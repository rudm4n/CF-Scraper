# Guida rapida: callingfans-scraper

## Comando unico

Ogni volta che vuoi scaricare, anche se la sessione è scaduta:

1. Apri callingfans.com in Firefox e controlla di essere loggato.
2. In un terminale:

```bash
~/cf-scraper/avvia.sh Queen_37
```

Lo script, in ordine:

1. crea l'ambiente Python se manca (solo la prima volta);
2. rilegge i cookie da Firefox, quindi una sessione scaduta si rinnova da sola;
3. scarica post e acquisti dei creator indicati.

Più creator insieme, separati da spazio:

```bash
~/cf-scraper/avvia.sh Queen_37 altro_creator
```

## Cosa aspettarsi

- Prima legge tutte le pagine del profilo: per Queen_37 (circa 1350 post) ci vogliono
  circa 10 minuti, con righe tipo `/ajax/updates: 300 post letti di 1354`.
- Poi scarica 4 file alla volta.
- Alla fine stampa `scaricati N, già presenti N, falliti N`.
- I file già scaricati vengono saltati: ogni giro prende solo il nuovo.
- Puoi interrompere con Ctrl+C e ripartire quando vuoi: non riscarica nulla.

## Dove sono i file

```
~/callingfans-downloads/<creator>/posts/image/...
~/callingfans-downloads/<creator>/posts/video/...
~/callingfans-downloads/<creator>/purchased/...
```

Per aprire la cartella: `xdg-open ~/callingfans-downloads`

## Problemi comuni

| Messaggio | Cosa fare |
|---|---|
| `Nessun cookie di callingfans.com nei profili Firefox` | Fai login su callingfans.com con Firefox e rilancia. |
| `sessione scaduta` / `Non risulti loggato` | Come sopra: login in Firefox, poi rilancia `avvia.sh`. |
| `HTTP 404` su alcuni video | File perso dal sito: non si apre neanche nel browser. Niente da fare. |
| `Permission denied` su `avvia.sh` | Esegui una volta `chmod +x ~/cf-scraper/avvia.sh`. |

## Aggiornare lo strumento

Quando ti dico che c'è una nuova versione:

```bash
cd ~/cf-scraper && git pull && .venv/bin/pip install -q -e .
```

## Comandi manuali (opzionali)

```bash
cd ~/cf-scraper && source .venv/bin/activate
callingfans-scraper auth --firefox                               # solo rinnovo cookie
callingfans-scraper scrape -u Queen_37 -a posts                  # solo post
callingfans-scraper scrape -u Queen_37 -a posts --dry-run        # elenca senza scaricare
callingfans-scraper config --save-dir ~/Scaricati/CF             # cambia cartella di destinazione
```

Nota sulla qualità: il sito ricomprime foto e video al caricamento e cancella gli originali.
Lo script scarica la versione più alta disponibile, la stessa che vedi nel browser.
