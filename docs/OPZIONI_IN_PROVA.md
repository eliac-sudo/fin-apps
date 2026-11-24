# Strategie sulle opzioni in prova sui dati futuri

Fissato il 6 novembre 2026, prima di qualunque entrata. Configurazione `config/options_forward_v1.json`, SHA-256 `00cfe78a0b8df89443a4d891bd96721236d9f38b83c1d10f73e5bb28b789e382`. Codice `bzd/option_paper.py`. Solo carta: nessun ordine, nessuna chiave. Non è consulenza finanziaria.

## Perché

Il test storico v3 ha usato opzioni ricostruite dagli indici di volatilità, perché lo storico gratuito delle catene non esiste. Qui le stesse idee, e altre, girano sui prezzi veri che il recorder salva da Deribit (ogni ora) e da Cboe (ogni 6 ore), dal 4 novembre 2026.

## Regole

- **Mercati:** SPY, QQQ, IWM, TLT, GLD, SLV, USO, FXE (Cboe) e BTC, ETH (Deribit).
- **Entrata:** una al giorno per mercato, dal 7 novembre 2026, sulla prima catena del giorno nella finestra: Deribit dalle 12:00 UTC, Cboe tra le 14:30 e le 21:00 UTC nei giorni feriali.
- **Scadenza:** quella più vicina a 30 giorni, tra 20 e 45.
- **Prezzi:** chi vende incassa il bid, chi compra paga l'ask. Commissioni: Deribit 0,03% del sottostante per gamba, al massimo 12,5% del prezzo; Cboe 0,65 dollari per contratto. Una gamba con spread oltre il 50% del prezzo medio non si apre.
- **Uscita:** a scadenza. Deribit sul prezzo di consegna della prima catena salvata dopo le 08:00 UTC; Cboe sulla chiusura del giorno.
- **Misura:** risultato in quota del premio (straddle, strangle, put) o del rischio massimo (iron condor, put spread).
- **Condizione:** volatilità implicita al centro della scadenza divisa per la previsione HAR fatta con i soli rendimenti precedenti al giorno di entrata. Sotto 0,9 economiche, sopra 1,25 care: le stesse soglie della v3.

| ID | Strategia | Quando | Base di confronto |
|---|---|---|---|
| V1 | Vendi straddle | ogni giorno | — |
| V2 | Vendi strangle 16Δ | ogni giorno | — |
| V3 | Iron condor 16Δ, ali 5Δ | ogni giorno | — |
| V4 | Put spread venduto 25Δ/10Δ | ogni giorno | — |
| V5 | Vendi put ATM (put-write) | ogni giorno | — |
| V6 | Compra straddle | ogni giorno | — |
| C1 | Compra straddle | opzioni economiche (O2 della v3) | V6 |
| C2 | Vendi straddle | opzioni care (O1 della v3) | V1 |
| C3 | Iron condor | opzioni care | V3 |

## Giudizio

Nessun giudizio prima del **6 novembre 2027** e di 100 operazioni chiuse per strategia. Fino ad allora l'app descrive e basta. Poi un test solo, con la correzione di Holm al 5%: per C1, C2 e C3 l'eccesso sulla loro base nello stesso mercato e mese; per V1–V6 il netto medio. Entrate dello stesso mercato che si sovrappongono contano come un cluster.

Il registro si ricostruisce dai file grezzi, che non si toccano: cambiare una regola cambia lo SHA, e il registro ricomincia da zero.

## Citate e non in prova

Calendar spread, risk reversal, put di protezione e gamma scalping sono descritte nell'app con fonti e motivo: a ognuna manca una regola (uscita, skew, copertura giornaliera) che va scritta prima di provarla.
