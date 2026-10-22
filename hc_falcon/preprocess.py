"""Java comment scanner preserving literals and token boundaries."""
VERSION = 'utf8_strict_bom_removed_lf_java_comments_removed_preserve_literals_v1'


def preprocess(content: bytes) -> str:
    text = content.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    result = []
    i = 0
    while i < len(text):
        if text.startswith('//', i):
            end = text.find('\n', i + 2)
            end = len(text) if end < 0 else end
            result.append(' ')
            i = end
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                raise ValueError('Unterminated Java comment')
            result.append(' ' + '\n' * text[i:end + 2].count('\n'))
            i = end + 2
        elif text[i] in ('"', "'"):
            delimiter = '"""' if text.startswith('"""', i) else text[i]
            start = i
            i += len(delimiter)
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                elif text.startswith(delimiter, i):
                    i += len(delimiter)
                    break
                else:
                    i += 1
            else:
                raise ValueError('Unterminated Java literal')
            result.append(text[start:i])
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)
