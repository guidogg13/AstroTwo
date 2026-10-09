# TEMPLATE-modulo.md — modello obbligatorio per ogni modulo

**Stato:** bozza

> Istruzioni per l'uso: questo file è il modello. Ogni file di modulo in `mdfiles/`
> deve contenere le stesse 14 sezioni, nello stesso ordine, con lo stesso livello
> di dettaglio. Le sezioni non si possono saltare. Se una sezione non è pertinente,
> si scrive esplicitamente "non applicabile" motivandolo in una riga.
> Le righe `<!-- ... -->` sono note per chi scrive il modulo e vanno cancellate
> nel file definitivo. I file nuovi hanno sempre stato `bozza`.

---

<!-- Il titolo del file deve corrispondere al nome file, senza estensione.
     Numerazione: 00-09 generali, 10-19 nucleo, 20-29 analisi, 30-39 IA,
     40-49 interfaccia, 50-59 funzioni avanzate, 60-69 distribuzione e test. -->

# NN-nome-modulo.md — <Nome leggibile del modulo>

**Stato:** bozza
<!-- ^ sezione 1 — Stato. Ammesso: bozza | in revisione | approvato.
     Solo uno stato `approvato` autorizza a scrivere codice per questo modulo.
     Deve comparire in testa a ogni file, come da CLAUDE.md. -->

## 2. Scopo

<!-- Una sola frase. Cosa risolve questo modulo per l'utente. -->

## 3. Cosa fa

<!-- Comportamento dettagliato, passo dopo passo.
     Deve bastare da solo: chi legge capisce il modulo senza leggere codice.
     Descrivere flussi, calcoli, effetti visibili, cosa viene persistito. -->

## 4. Cosa NON fa

<!-- Confini netti. Elenco puntato di ciò che il modulo non tratta,
     anche se sarebbe "naturale" aspettarselo. Serve a evitare sovrapposizioni. -->

## 5. Livello e dipendenze

- **Livello:** 1 | 2 | 3 | 4
  <!-- 1 = nucleo (pari ad Aladin), 2 = analisi, 3 = IA, 4 = funzioni avanzate.
       Un livello non rompe mai quello sotto. -->
- **Dipende da:** <!-- moduli (file .md) su cui questo si appoggia. Se nessuno, "nessuno" -->
- **Usato da:** <!-- moduli che usano questo. Se nessuno, "nessuno" -->

## 6. Input e output

<!-- Per ogni input/output: nome, tipo, unità di misura, formato, intervallo valido.
     Esempio: "ra — float, gradi, ICRS J2000, [0,360)".
     Specificare sempre unità e sistema di riferimento (vedi 02-convenzioni.md). -->

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | | | | |
| out | | | | |

## 7. Interfaccia pubblica

<!-- Funzioni e classi previste, in forma descrittiva: nome, responsabilità,
     parametri e valori di ritorno in parole. NIENTE CODICE in questa fase. -->

- **`NomeFunzione`** — descrizione, parametri, cosa restituisce.
- **`NomeClasse`** — responsabilità, metodi principali in parole.

## 8. Librerie e standard di riferimento

<!-- Solo librerie consolidate e standard già usati nella comunità scientifica.
     Per ciascuna: cosa se ne usa e perché. Se una scelta non è ancora presa,
     scriverla in "Decisioni aperte" invece di sceglierla in silenzio.
     Se il modulo non usa libreria né standard, scrivere "non applicabile". -->

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| | | |

## 9. Regole e vincoli

<!-- Vincoli non negoziabili: precisione, sistemi di riferimento, unità,
     gestione dei tempi, prestazioni, determinismo, riproducibilità.
     Ogni numero mostrato all'utente deve essere calcolato da codice testato,
     mai dall'IA (regola d'oro n. 1). -->

## 10. Casi limite ed errori

<!-- Cosa succede in situazioni limite: dati mancanti, coordinate fuori campo,
     rete assente, file corrotti, parametri fuori intervallo.
     Per ciascuno: comportamento visibile e codice/identificatore dell'errore. -->

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| | | |

## 11. Esposizione all'IA

<!-- Se il modulo è uno strumento che l'IA può invocare: nome dello strumento,
     parametri accettati, cosa restituisce, chi calcola i numeri (mai l'IA).
     Se il modulo non è uno strumento per l'IA: "non applicabile" + una riga di motivo. -->

## 12. Test di accettazione

<!-- Esempi con valori ricalcolabili con una libreria consolidata (Astropy,
     astroquery, healpy, ecc.). Per ogni test: passi, valore atteso, come verificarlo.
     Non scrivere numeri di cui non si è certi: usare "da verificare" oppure
     indicare l'espressione che il tester deve calcolare con la libreria. -->

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | | | | |

## 13. Decisioni aperte

<!-- Tutto ciò che ancora non è deciso: tecnologia, formato, comportamento.
     Non scegliere in silenzio. Ogni voce: cosa manca, perché conta, opzioni possibili. -->

- **D1 — <titolo>:** <cosa manca>. Opzioni: <a> | <b>. Da decidere.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| YYYY-MM-DD | | Creazione del file (stato: bozza) |
