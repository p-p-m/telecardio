# # This code tries to read file
# path = '/Users/pavel.m/Documents/AAS10IL34Q.ZHR'
# # path = '/Users/pavel.m/Documents/AAS10XWL12.ZHR'
# f = open(path, mode='r', encoding="windows-1251", errors="ignore")
# lines = []
# for i, l in enumerate(f):
#     print(i, l)
#     lines.append(l)
#     if 'Доп. поле №1' in l:
#         print('found')
#         break
#     if i > 30:
#         break
# f.close()