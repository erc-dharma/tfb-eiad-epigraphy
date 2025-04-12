import sys, tokenize, io, re, sqlite3, json
from dharma import tree, biblio

def patch_vowels(t):
	# ° + vowel -> ° + capitalized vowel
	def repl(m):
		return m.group(1).capitalize()
	for s in t.strings():
		r = re.sub("°([aāiīuūeo]|r\N{combining ring below})", repl, s.data)
		s.replace_with(r)

tpl = tree.parse_string(
"""	<respStmt>
		<resp>author of digital edition</resp>
		<persName ref="part:argr">
			<forename>Arlo</forename>
			<surname>Griffiths</surname>
		</persName>
		<persName ref="part:vito">
			<forename>Vincent</forename>
			<surname>Tournier</surname>
		</persName>
	</respStmt>""")

def patch_resps(t):
	# In the teiHeaders of all files that contain any instance of part:jodo, please change the entire string of <resptStmt>s after <title> to become
	for node in t.find("//teiHeader/fileDesc/titleStmt/respStmt/persName[@ref]"):
		if node["ref"].removeprefix("part:") == "jodo":
			break
	else:
		return
	nodes = t.find("//teiHeader/fileDesc/titleStmt/respStmt")
	for node in nodes[1:]:
		node.delete()
	nodes[0].replace_with(tpl.root.copy())

# for f in sys.argv[1:]:
# 	try:
# 		t = tree.parse(f)
# 	except tree.Error:
# 		continue
# 	#patch_resps(t)
# 	#with open(f, "w") as f:
# 	#	f.write(t.xml())

def trigrams(s):
	return (s[i:i + 3] for i in range(len(s) - 3 + 1))

def jaccard(s, t):
	ngrams1 = set(trigrams(s))
	ngrams2 = set(trigrams(t))
	try:
		inter = len(ngrams1 & ngrams2)
		return inter / (len(ngrams1) + len(ngrams2) - inter)
	except ZeroDivisionError:
		return 0

new = {}

db = sqlite3.connect("/home/michael/dharma/dbs/texts.sqlite")
for short_title, data in db.execute("select short_title, data from biblio"):
	data = json.loads(data)
	title = re.sub("<.+?>", "", data["title"])
	names = []
	for creator in data["creators"]:
		if creator.get("lastName"):
			name = creator["firstName"] + " " + creator["lastName"]
		else:
			name = creator["name"]
		names.append(name.strip())
	names = sorted(set(names))
	s = "  " + "  ".join(names) + "  " + title + "  "
	new[short_title] = s

old = {}

for struct in tree.parse("EIAD_bibliography.xml").find("//biblStruct"):
	short_title = struct["id"]
	if not short_title:
		continue
	title = struct.first(".//title[@level='a' or @level='m']").text()
	names = []
	for creator in struct.find(".//author") + struct.find(".//editor"):
		if creator.first("surname"):
			name = creator.first("forename").text() + " " + creator.first("surname").text()
		else:
			name = creator.first("name").text()
		names.append(name.strip())
	names = sorted(set(names))
	s = "  " + "  ".join(names) + "  " + title + "  "
	old[short_title] = s

def levenshtein(a, b):
	if a == b:
		return 0
	if len(a) == 0:
		return len(b)
	if len(b) == 0:
		return len(a)

	prev_row = list(range(len(b) + 1))
	curr_row = [0] * (len(b) + 1)

	for i, ca in enumerate(a, 1):
		curr_row[0] = i
		for j, cb in enumerate(b, 1):
			insert_cost = curr_row[j - 1] + 1
			delete_cost = prev_row[j] + 1
			replace_cost = prev_row[j - 1] + (ca != cb)
			curr_row[j] = min(insert_cost, delete_cost, replace_cost)
		prev_row, curr_row = curr_row, prev_row

	return prev_row[-1]

def find_best_match(old_short_title, old_rec):
	ret = []
	for new_short_title, new_rec in new.items():
		j = levenshtein(new_rec, old_rec)
		# print(repr(old_rec))
		# print(repr(new_rec))
		# print(j)
		# print("---")
		ret.append((j, new_short_title, old_rec, new_rec))
	ret.sort()
	return ret[0][1]

for line in sys.stdin:
	sys.stdout.flush()
	short_title = line.strip()
	rec = old.get(short_title)
	if not rec:
		print(short_title)
		continue
	match = find_best_match(short_title, rec)
	print(short_title, match)
