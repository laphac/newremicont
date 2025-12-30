# url_decode.py
def url_decode(s):
    if not s or '%' not in s:
        return s.replace('+', ' ')
    res = []
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            try:
                char = chr(int(s[i+1:i+3], 16))
                res.append(char)
                i += 3
                continue
            except:
                pass
        res.append(' ' if s[i] == '+' else s[i])
        i += 1
    return ''.join(res)