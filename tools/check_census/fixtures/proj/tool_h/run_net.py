# 外向きを使う検証に見立てた合成 script。通信はせず、外向きの既定が落ちていることを見て落ちる
import os, sys
if os.environ.get("https_proxy", "").endswith(":9"):
    print("外向きの既定が落ちているので検証できない")
    sys.exit(1)
print("1 passed")
