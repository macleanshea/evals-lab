"""Write inspect/logs-www/vercel.json after each `inspect view bundle`.

Tells Vercel this is a plain static folder (no framework, no build step) and
serves the viewer's own Content-Security-Policy, which the bundle writes to
content-security-policy.json (its script hashes change between Inspect versions,
so this is regenerated every time rather than hand-edited).
"""
import json
import pathlib

www = pathlib.Path(__file__).parent / "logs-www"
csp = json.loads((www / "content-security-policy.json").read_text())
header = "; ".join(f"{k} {' '.join(v)}" for k, v in csp["directives"].items())
config = {
    "$schema": "https://openapi.vercel.sh/vercel.json",
    "framework": None,
    "buildCommand": "",
    "installCommand": "",
    "outputDirectory": ".",
    "headers": [
        {"source": "/(.*)", "headers": [{"key": "Content-Security-Policy", "value": header}]},
        # .eval logs are zip archives. Vercel doesn't know the extension and serves
        # them compressed, with no Content-Length and no byte ranges; the viewer
        # needs one of those ("Could not determine content length"). As
        # application/zip they are served as-is, with both.
        {"source": "/logs/(.*)\\.eval", "headers": [{"key": "Content-Type", "value": "application/zip"}]},
    ],
}
(www / "vercel.json").write_text(json.dumps(config, indent=2) + "\n")
print(f"Wrote {www / 'vercel.json'}")
