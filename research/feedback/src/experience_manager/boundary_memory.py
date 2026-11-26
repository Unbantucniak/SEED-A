"""Reuse verified word boundaries and letter case in a portable identifier converter.

Input and response must preserve the ordered ASCII letters/digits for a
character-level correction. If not, the caller's draft is kept intact.
"""
from collections import Counter, defaultdict
import re

from .identifier_conventions import STYLE_GROUP


def units(text):
    chars=[]
    marks=[]
    offset=0
    for match in re.finditer("[A-Za-z0-9]",text):
        chars.append(match.group())
        marks.append(text[offset:match.start()])
        offset=match.end()
    return chars,marks,text[offset:]


def category(c):
    return "D" if c.isdigit() else "U" if c.isupper() else "L"


def roles(chars,marks):
    types=["^"]+[category(c) for c in chars]+["$"]
    for i,mark in enumerate(marks):
        prev,cur,nxt=types[i:i+3]
        before=mark if mark else ""
        # Class repeated delimiters together without treating a dot as an underscore.
        sep="".join(dict.fromkeys(before))
        start=i==0
        context=(start,prev,cur,nxt,sep)
        coarse=(start,prev,cur,nxt,bool(mark))
        yield context,coarse


def aligned(text,output):
    a,marks,_=units(text)
    b,edges,tail=units(output)
    if not a or tail or "".join(a).lower()!="".join(b).lower():
        return None
    return a,marks,b,edges


class BoundaryMemory:
    def __init__(self,history):
        self.votes=defaultdict(Counter)
        self.separators={}
        self.endings=defaultdict(Counter)
        for style,text,out in history:
            pair=aligned(text,out)
            if pair is None:continue
            a,marks,b,edges=pair
            style_group=STYLE_GROUP[style]
            # One occurrence per feature and source input so long names have no extra vote.
            observations=set()
            for i,(fine,coarse) in enumerate(roles(a,marks)):
                bit=bool(edges[i])
                upper=b[i].isupper()
                for level,ctx in (("exact",fine),("coarse",coarse)):
                    observations.add((("case",style,level,ctx),upper))
                    observations.add((("mark",style,level,ctx),edges[i]))
                    if style_group=="separated" and i>0:
                        observations.add((("boundary","separated",level,ctx),bit))
                if edges[i] and i>0:self.endings[style][edges[i]]+=1
            for key,val in observations:self.votes[key][val]+=1
        for style,counter in self.endings.items():
            self.separators[style]=counter.most_common(1)[0][0]

    def _choice(self,typ,scope,fine,coarse,force):
        for key in ((typ,scope,"exact",fine),(typ,scope,"coarse",coarse)):
            counts=self.votes.get(key)
            if counts:
                order=sorted(counts.items(),key=lambda p:(-p[1],str(p[0])))
                if force or (order[0][1]>=2 and (len(order)==1 or order[0][1]>=3*order[1][1])):
                    return order[0][0]
                return None
        return None

    def apply(self,style,text,draft,force=False):
        if not isinstance(draft,str):return draft,0
        pair=aligned(text,draft)
        if pair is None:return draft,0
        a,marks,b,edges=pair
        pieces=[]
        changed=0
        for i,(fine,coarse) in enumerate(roles(a,marks)):
            mark=self._choice("mark",style,fine,coarse,force)
            upper=self._choice("case",style,fine,coarse,force)
            boundary=self._choice("boundary","separated",fine,coarse,force) if i else None
            if mark is None and STYLE_GROUP[style]=="separated" and boundary is not None:
                mark=self.separators.get(style) if boundary else ""
            if upper is None and style in ("camel","pascal") and boundary is not None and a[i].isalpha():
                # A confirmed word boundary can start a new word. Other letter positions keep the paid draft.
                if boundary:upper=True
            literal=b[i] if upper is None else a[i].upper() if upper else a[i].lower()
            glue=edges[i] if mark is None else mark
            pieces.append(glue+literal)
            changed+=int(literal!=b[i] or glue!=edges[i])
        return "".join(pieces),changed
