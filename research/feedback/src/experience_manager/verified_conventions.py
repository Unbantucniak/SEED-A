"""An explicit common-specification check and a version-bound contradiction veto."""
from .identifier_conventions import RULES,STYLE_GROUP,model,signature


class VerifiedConventions:
    def __init__(self,style,specification,history):
        self.style=style
        self.pool=[r for r in RULES if all(model(r,style,x)==y for x,y in specification)]
        self.events=[(s,signature(x),[model(r,s,x)==y for r in self.pool]) for s,x,y in history]
        self.cache={}

    def shortlist(self,shape):
        if shape in self.cache:return self.cache[shape]
        scores=[0]*len(self.pool)
        challenges=[]
        for s,pattern,matches in self.events:
            weight=1+int(STYLE_GROUP[s]==STYLE_GROUP[self.style])+2*int(s==self.style)+3*int(shape==pattern)
            for i,correct in enumerate(matches):
                if correct:scores[i]+=weight
            if s==self.style and shape==pattern:
                challenges.append(matches)
        best=max(scores,default=None)
        rules=[self.pool[i] for i,score in enumerate(scores) if score==best and all(match[i] for match in challenges)]
        self.cache[shape]=rules
        return rules

    def infer(self,text,force=False):
        if not text.isascii():return None
        candidates=self.shortlist(signature(text))
        if not candidates:return None
        result=model(candidates[0],self.style,text)
        if not force and any(model(r,self.style,text)!=result for r in candidates[1:]):return None
        return result
