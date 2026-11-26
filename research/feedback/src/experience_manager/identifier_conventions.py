"""Infer a project's identifier conventions from completed, version-scoped native observations."""
from functools import lru_cache
from itertools import product
import re


RULES=tuple(product((True,False),(True,False),("attached","split","after","before","upper"),
                    ("split","drop"),("normalize","acronyms","tail"),(False,True)))
STYLE_GROUP={"camel":"joined","pascal":"joined","snake":"separated","kebab":"separated",
             "constant":"separated","dot":"separated","space":"separated","path":"separated","train":"separated"}


@lru_cache(maxsize=65536)
def pieces(text,lower_upper,acronym,digit,punctuation):
    if punctuation=="drop":
        text=re.sub(r"[^A-Za-z0-9_ .\t/-]","",text)
    if acronym:
        text=re.sub(r"([A-Z])([A-Z][a-z])",r"\1 \2",text)
    if lower_upper:
        text=re.sub(r"([a-z])([A-Z])",r"\1 \2",text)
    if digit in ("split","before"):
        text=re.sub(r"([a-zA-Z])([0-9])",r"\1 \2",text)
    if digit in ("split","after"):
        text=re.sub(r"([0-9])([a-zA-Z])",r"\1 \2",text)
    elif digit=="upper":
        text=re.sub(r"([0-9])([A-Z])",r"\1 \2",text)
    return tuple(re.findall(r"[A-Za-z0-9]+",text))


@lru_cache(maxsize=262144)
def model(rule,style,text):
    words=pieces(text,*rule[:4])
    if not words:return ""
    def title(w):
        if rule[4]=="acronyms" and w.isupper():return w
        return w[0].upper()+(w[1:] if rule[4]=="tail" else w[1:].lower())
    if style in ("pascal","camel"):
        out=[]
        for i,w in enumerate(words):
            if style=="camel" and i==0:
                out.append(w.lower() if rule[4]!="tail" else w[0].lower()+w[1:])
            else:
                out.append(("_" if i and rule[5] and w[0].isdigit() else "")+title(w))
        return "".join(out)
    sep={"constant":"_","snake":"_","kebab":"-","dot":".","space":" ","path":"/","train":"-"}[style]
    if style=="train":return sep.join(title(w) for w in words)
    joined=sep.join(words)
    return joined.upper() if style=="constant" else joined.lower()


def signature(text):
    return (bool(re.search("[A-Z]{2}[a-z]|[A-Z]{2,}",text)),bool(re.search("[a-z][A-Z]",text)),
            bool(re.search("[0-9]",text)),bool(re.search("[^A-Za-z0-9 _-]",text)),bool(re.search("[ _-]",text)))


class ConventionGate:
    """A rule may replace the paid draft only when the strongest explanations agree.

    Earlier records are the native results of already completed activities. A
    closer input shape, identical style, or same renderer family gets more weight.
    """
    def __init__(self, observations):
        self.observations=[]
        for style,source,target in observations:
            good=tuple(i for i,r in enumerate(RULES) if model(r,style,source)==target)
            self.observations.append((style,signature(source),good))
        self.cache={}

    def candidates(self,style,shape,nearest):
        key=(style,shape,nearest)
        if key in self.cache:return self.cache[key]
        history=[]
        for i,(past,sig,good) in enumerate(self.observations):
            common=sum(a==b for a,b in zip(shape,sig))
            weight=1+int(STYLE_GROUP[style]==STYLE_GROUP[past])+2*int(style==past)+3*int(shape==sig)
            history.append((common,int(past==style),int(STYLE_GROUP[past]==STYLE_GROUP[style]),i,weight,good))
        if nearest and history:history=[max(history)]
        scores=[0]*len(RULES)
        for *_,weight,good in history:
            for i in good:scores[i]+=weight
        maximum=max(scores)
        result=tuple(i for i,s in enumerate(scores) if s==maximum)
        self.cache[key]=result
        return result

    def infer(self,style,text,policy="selective"):
        if not text.isascii():return None
        if policy=="static":return model(RULES[0],style,text)
        best=self.candidates(style,signature(text),policy=="nearest")
        result=model(RULES[best[0]],style,text)
        if policy in ("always","nearest"):return result
        if any(model(RULES[i],style,text)!=result for i in best[1:]):return None
        return result
