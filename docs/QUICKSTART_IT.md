# Guida rapida — Community Edition

Versione candidata **0.1.0-alpha.1**, sperimentale e non ancora pubblicata.
Licenza Apache-2.0, con [testo completo](../LICENSE) incluso.

Copyright 2026 Armando Graziani

Artemis Bloom Studios è il nome commerciale e l'identità del progetto.
Interfacce incluse: CLI e Python; nessuna console web o connessione automatica
a un assistente. Nessuna chiave API e nessun download di modelli.

Servono Python 3.11+ e SQLite FTS5 su sistema POSIX. Verifica locale effettuata
su macOS arm64 con Python 3.14.2 e SQLite 3.51.1; Windows non supportato, Linux e
altre versioni Python ancora da verificare.

Estrai lo ZIP sorgente in una cartella nuova e apri lì il Terminale:

```sh
trial_dir="$(mktemp -d)"
trial_dir="$(cd "$trial_dir" && pwd -P)"
python3 -B install.py --output "$trial_dir/artemis-memory-core.pyz"
python3 -B "$trial_dir/artemis-memory-core.pyz" demo --state "$trial_dir/demo-state"
python3 -B "$trial_dir/artemis-memory-core.pyz" search --state "$trial_dir/demo-state" lantern --limit 2
```

La demo crea soltanto dati inventati, contrassegnati come sintetici. Copia uno
degli ID restituiti, poi esegui (sostituendo `SOURCE_ID`):

```sh
python3 -B "$trial_dir/artemis-memory-core.pyz" fetch --state "$trial_dir/demo-state" SOURCE_ID --limit 600
```

La risposta comprende testo, provenienza dichiarata, impronte, classificazione,
offset e relazioni fra versioni. `next_start` indica la pagina seguente del testo;
`next_cursor` serve invece a proseguire la ricerca. Non sono intercambiabili.
Una nuova edizione non equivale a una rettifica: solo `corrects` dichiara questa
relazione. Una data ignota resta ignota.

Per le tue fonti usa il [formato capsula](FORMAT.md), una cartella di stato
separata, `init`, `preview` e infine `import` con l'impronta esatta approvata.
Gli originali vengono conservati in copie locali; l'indice è derivato.
`revoke` impedisce nuovi recuperi dall'engine, senza cancellare le copie né le
risposte già ottenute. Nessuna scansione automatica delle cartelle personali.

Se appare `BLOCKED`, conserva il codice d'errore e verifica le istruzioni del
README. Non allegare dati reali o credenziali alle segnalazioni. Per disinstallare,
rimuovi il file `.pyz`; valuta separatamente se conservare la cartella dei dati.

Il software permette di ritrovare fonti. Le impronte ne verificano la coerenza
rispetto al registro locale, non la verità storica né l'assenza di dati riservati.

Questa alpha non è un ambiente per eseguire codice ostile. Operatore, programma
installato e registro locale devono essere attendibili. L'isolamento imposto
dal sistema operativo non è stato verificabile nell'ambiente di preparazione;
una HOME temporanea o una virtualenv non sono una sandbox del filesystem.
