import subprocess
import sys
import json
import os
import re

J = os.path.expanduser("~/Applications/topcat/topcat-full.jar")
texts = json.load(open(sys.argv[1]))
res = {}
for t in texts:
    res[t] = {}
    for syn in ("vounits", "fits"):
        p = subprocess.run(
            ["java", "-cp", J, "uk.me.nxg.unity.UnitParser", f"-i{syn}", "-v", t], capture_output=True, text=True
        )
        o = p.stdout + p.stderr
        if "rror" in o and "check:" not in o:
            res[t][syn] = "sintassi non valida"
            continue
        def g(k):
            return re.search(k + r"\?\s+(\w+)", o)
        rec, recm, con = g("recognised"), g("recommended"), g("constraints satisfied")
        res[t][syn] = (
            f"riconosciute={rec.group(1) if rec else '?'} raccomandate={recm.group(1) if recm else '?'} vincoli={con.group(1) if con else '?'}"
        )
json.dump(res, open(sys.argv[2], "w"), indent=1)
for t, v in res.items():
    print(f"{t!r:42} VOU: {v['vounits']:55} FITS: {v['fits']}")
