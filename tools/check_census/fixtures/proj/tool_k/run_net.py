# 同じ script を allow_network=はい の行から呼ぶ(宣言で許した側)
import os, sys
if os.environ.get("https_proxy", "").endswith(":9"):
    print("外向きの既定が落ちているので検証できない")
    sys.exit(1)
print("1 passed")
