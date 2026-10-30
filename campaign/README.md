# Campaign Studio

Įkeliate vieną produkto nuotrauką ir gaunate 360 kampaniją viename vizualiniame stiliuje:

- 3–9 socialinių tinklų kadrus (HERO, PORTRAIT, LIFESTYLE, DETAIL, BEAUTY, ENVIRONMENT, RITUAL, REFLECTION, CLOSING) su tekstais ir grotažymėmis;
- 3 Meta reklamas (9:16 PNG su antrašte ir CTA mygtuku);
- svetainės „hero“ banerį;
- email laišką (HTML, tinkamą ir telefonui);
- kampanijos lentą ir ZIP su visais failais.

## Kaip veikia

1. **Claude** (`claude-opus-5-5`) peržiūri produkto nuotrauką, aprašymą ir pasirinktinai stiliaus pavyzdį. Parašo kampanijos „bibliją“: koncepciją, paletę, stilių, lokaciją, vieną nuolatinį (išgalvotą) modelį, kiekvieno kadro sceną ir visus tekstus.
2. **Gemini image** (`IMAGE_MODEL`, numatytasis `gemini-2.5-flash-image`) pirmiausia sugeneruoja HERO kadrą. Kiti kadrai, reklamos ir baneris generuojami lygiagrečiai, kaip pavyzdžius naudojant produkto nuotrauką ir HERO kadrą. Taip išlaikomas tas pats modelis, šviesa ir spalvos.
3. Reklamų tekstai uždedami atskiru sluoksniu (Pillow), o ne generuojami modeliu, todėl visada lieka įskaitomi.

Be API raktų programa veikia **demo režimu**: tekstai būna pavyzdiniai, o vaizdai yra maketai su jūsų produktu. Taip galima išbandyti visą eigą nemokamai.

## Paleidimas

```bash
cd campaign
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # tekstams ir koncepcijai
export GEMINI_API_KEY=...      # vaizdams
python app.py
```

Atidarykite http://127.0.0.1:5000. Rezultatai saugomi `campaign/runs/`.

## Pastabos

- Viena kampanija su 9 kadrais sukuria 13 vaizdų.
- Prieš naudodami vaizdus reklamoje, patikrinkite etiketės tikslumą: modelis kartais iškraipo smulkų tekstą.
- Pagal ES DI aktą ir Meta taisykles DI sukurtą turinį gali tekti pažymėti.
