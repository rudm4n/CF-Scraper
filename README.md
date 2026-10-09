# callingfans-scraper

CLI Python ispirata a [of-scraper](https://github.com/datawhores/OF-Scraper) per archiviare
in locale i contenuti dei creator a cui **sei abbonato** su CallingFans: post, messaggi,
storie, highlights e acquisti.

Usa la sessione del tuo browser (cookie + header), quindi scarica solo quello che il tuo
account può già vedere.

> **Stato**
>
> | Sezione | Stato |
> |---|---|
> | Post di un creator | implementato (`/ajax/updates`), da provare con sessione reale |
> | Acquisti (PPV) | implementato (`/ajax/user/purchases`), da provare con sessione reale |
> | Lista abbonamenti | da mappare: per ora indica i creator con `-u` |
> | Messaggi, storie, highlights | da mappare: servono pagine HTML di esempio |
>
> Il sito è basato su Sponzy (Laravel): gli endpoint restituiscono HTML, non JSON.
> I post PPV non comprati vengono saltati.

## Installazione

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Uso

```bash
callingfans-scraper auth                      # incolla header Cookie e User-Agent del browser
callingfans-scraper config --save-dir ~/CF    # opzionale
callingfans-scraper scrape -u alice bob -a posts purchased
callingfans-scraper scrape -u alice --dry-run  # elenca senza scaricare
```

I file finiscono in `save_dir` secondo `filename_template`, che di default è:

```
{username}/{area}/{media_type}/{date}_{post_id}_{media_id}.{ext}
```

Campi disponibili: `username`, `creator_id`, `area`, `media_type`, `post_id`, `media_id`,
`date`, `ext`.

I media già scaricati sono registrati in `save_dir/.callingfans.db` e vengono saltati nei
giri successivi.

## File locali

- `~/.config/callingfans-scraper/config.json`: configurazione.
- `~/.config/callingfans-scraper/auth.json`: credenziali, salvate con permessi 600. **Non
  committarlo e non condividerlo.**

## Test

```bash
pip install -e '.[dev]' && pytest
```
