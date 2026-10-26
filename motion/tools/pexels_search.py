import json,sys,urllib.request,urllib.parse,os
out=sys.argv[1]; qs=json.loads(sys.argv[2])
res={}
for key,q in qs.items():
    u='https://api.pexels.com/v1/search?'+urllib.parse.urlencode({'query':q,'per_page':6,'orientation':'portrait'})
    d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'skillora'})))
    res[key]=[{'id':p['id'],'src':p['src']['large'],'big':p['src']['large2x'],'by':p['photographer'],'url':p['url'],'alt':p.get('alt','')} for p in d['photos']]
    for i,p in enumerate(res[key]):
        open(f'{out}/{key}_{i}.jpg','wb').write(urllib.request.urlopen(urllib.request.Request(p['src'],headers={'User-Agent':'Mozilla/5.0'})).read())
json.dump(res,open(f'{out}/res.json','w'),indent=1)
print({k:len(v) for k,v in res.items()})
