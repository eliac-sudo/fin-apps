---
title: Agenti di ricerca
kind: calcolo
status: ogni mese sul server, a pagamento entro il tetto
brief: Ogni mese cerca lavori nuovi e chi cita quelli letti; il lettore (Haiku) scrive note sugli abstract, il supervisore (Opus) le ricontrolla e propone bozze di setup «non testate».
code: bzd/research.py#discover, bzd/research.py#room_for_research, bzd/literature.py#citing, bzd/research.py#read_paper, bzd/research.py#check_note, bzd/research.py#check_review, bzd/research.py#draft_ideas, bzd/research.py#estimate
docs: docs/letteratura/NOTE.md, docs/letteratura/IDEE_V2.md
data: data/literature
feeds: v2
---
## Come funziona
- **Ogni mese** (il 1° alle 05:00 UTC, timer `bzd-research` sul server) `python -m bzd.research mese --paga` fa tre passi. Prima cerca, gratis (`bzd/research.py#discover`): rifà le ricerche per tema su OpenAlex e arXiv, anche solo sugli ultimi due anni, e prende i lavori più citati che citano fino a 15 note già lette con pertinenza alta o media e non scartate dal supervisore (`bzd/literature.py#citing`). Poi il lettore legge tutto ciò che è nuovo, e alla fine parte il supervisore se è il momento.
- La ricerca si ferma 0,50 $ sotto il tetto mensile, così al revisore degli [[agenti-alert]] resta budget (`bzd/research.py#room_for_research`). Il tetto è 3 $ dal 24 novembre 2026.
- `python -m bzd.research stima` dice quanto costerebbe, gratis; `python -m bzd.research scopri` fa solo la ricerca.
- Il **lettore** legge l'abstract di un lavoro della [[letteratura]] e scrive una nota; il codice scarta citazioni e numeri senza fonte (`bzd/research.py#check_note`).
- Il **supervisore** ricontrolla ogni nota sul suo abstract (regge, da correggere, forzata) e scrive bozze solo dalle note che reggono.

## Stato
Primo giro il 6 novembre: 13 note, 10 reggono, 3 forzate. Una bozza, il trend lungo, è diventata la pre-registrazione [[v2]]. Il 24 novembre il lettore ha cominciato a leggere tutto il catalogo (352 lavori), su richiesta dell'utente.
