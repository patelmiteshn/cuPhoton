"""Embed shared theme assets so the existing static allowlist needs no changes."""
from pathlib import Path
import re
base=Path(__file__).resolve().parent
block='<!-- photon-theme:start --><style>\n'+(base/'theme.css').read_text()+'\n</style><script>\n'+(base/'theme.js').read_text()+'\n</script><!-- photon-theme:end -->'
for name in ('index.html','gpu.html'):
    p=base/name
    s=p.read_text()
    s=re.sub(r'<!-- photon-theme:start -->.*?<!-- photon-theme:end -->','',s,flags=re.S)
    s=s.replace('</head>',block+'</head>')
    if name=='gpu.html':
        s=s.replace('<body>','<body class="gpu-page">')
        s=s.replace("x.strokeStyle='#283449'","x.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--line').trim()")
        s=s.replace("x.fillStyle='#9aaac0'","x.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--muted').trim()")
        s=s.replace("x.strokeStyle='#8ce6bf'","x.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--mint').trim()")
    p.write_text(s)
