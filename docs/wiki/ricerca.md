---
title: Agenti di ricerca
kind: calcolo
status: a pagamento, solo col via dell'utente
brief: Il lettore (Haiku) scrive note sugli abstract, il supervisore (Opus) le ricontrolla e propone bozze di setup «non testate».
code: bzd/research.py#read_paper, bzd/research.py#check_note, bzd/research.py#check_review, bzd/research.py#draft_ideas, bzd/research.py#estimate
docs: docs/letteratura/NOTE.md, docs/letteratura/IDEE_V2.md
data: data/literature
feeds: v2
---
## Come funziona
- `python -m bzd.research stima` dice quanto costerebbe, gratis.
- Il **lettore** legge l'abstract di un lavoro della [[letteratura]] e scrive una nota; il codice scarta citazioni e numeri senza fonte (`bzd/research.py#check_note`).
- Il **supervisore** ricontrolla ogni nota sul suo abstract (regge, da correggere, forzata) e scrive bozze solo dalle note che reggono.

## Stato
Primo giro il 6 novembre: 13 note, 10 reggono, 3 forzate. Una bozza, il trend lungo, è diventata la pre-registrazione [[v2]].
