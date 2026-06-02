# Source-Selection Golden Results

Checked at: 2026-06-02T13:51:20+00:00
Query model: `deepseek-v4-flash`
Query base URL: `https://api.deepseek.com`
Mode: `hybrid`
Source limit: `8`
Flags: `RERANKER_ENABLED=False`, `HYBRID_SYNTH_ENABLED=True`, `HYBRID_QUERY_CARDS_ENABLED=True`, `WIKI_ENABLED=True`

Summary: 10/10 passed, avg=100.0, avg_duration=5.216s

| Case | Score | Pass | Rank | Missing | Top-forbidden |
|---|---:|:---:|---:|---|---|
| f1_trump_orban_source | 100 | Y | 1 | - | - |
| ultra_left_right_similarity_source | 100 | Y | 1 | - | - |
| cuba_talks_source | 100 | Y | 1 | - | - |
| q9_cuba_protests_source | 100 | Y | 1 | - | - |
| cuba_pressure_deal_source | 100 | Y | 1 | - | - |
| narva_plans_source | 100 | Y | 1 | - | - |
| q22_narva_visuals_top_source | 100 | Y | 1 | - | - |
| afd_ukraine_stance_source | 100 | Y | 1 | - | - |
| afd_nepotism_source | 100 | Y | 1 | - | - |
| north_korea_troops_source | 100 | Y | 1 | - | - |

## f1_trump_orban_source

Question: Трамп реально поддерживал Орбана? Дай источник.

Profile: `source`

Note: Historical F1 source-grounding case: support for Orban should resolve to direct Hungary/Slovakia posts.

Да, в предоставленных источниках есть информация о том, что Дональд Трамп выражал поддержку премьер-министру Венгрии Виктору Орбану. В частности, в одном из сообщений (источник: https://t.me/c/3328128766/133) описывается телефонный разговор Трампа с участниками митинга в поддержку Орбана, где Трамп назвал Орбана «фантастическим лидером», похвалил его за защиту Венгрии от миграции и заявил, что любит Венгрию и Орбана. В другом посте (источник: https://t.me/c/3328128766/148) утверждается, что Трамп открыто поддержал переизбрание Орбана на выборах 2026 года, призвав венгров голосовать за него.

Кроме того, в контексте упоминается статья Bloomberg, где говорится, что ультраправые партии в Европ...

Sources:
- 1. https://t.me/c/3328128766/133 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\133.txt
- 2. https://t.me/c/3328128766/148 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\148.txt
- 3. https://t.me/c/3328128766/123 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\123.txt
- 4. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 7. https://t.me/c/3299898370/24 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\24.txt
- 8. https://t.me/c/3328128766/181 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\181.txt

## ultra_left_right_similarity_source

Question: Что в базе говорится о сходстве ультралевых и ультраправых?

Profile: `answer`

Note: The direct similarity claim is canonical in normalized source 11.

В базе данных содержатся утверждения о том, что ультралевые и ультраправые могут быть схожи или совпадать. В одном из документов говорится: «Ультралевые и ультраправые совпадают», а в другом приводится утверждение «Везде ультралевые и ультраправые одинаковые».

В качестве примера такого сходства приводится ситуация вокруг председателя Европейской комиссии Урсулы фон дер Ляйен. Согласно источникам, её политика вызывает ненависть как у ультраправых, так и у ультралевых сил Европы, несмотря на их идеологическую противоположность. Ультраправые критикуют её за слишком либеральную миграционную политику и «Зелёный курс», тогда как ультралевые обвиняют её в милитаризации ЕС и поддержке крупного биз...

Sources:
- 1. https://t.me/c/3299898370/11 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\11.txt
- 2. https://t.me/c/3299898370/20 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\20.txt
- 3. https://t.me/c/3299898370/21 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\21.txt
- 4. https://t.me/c/3299898370/22 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\22.txt
- 5. https://t.me/c/3328128766/30 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\30.txt
- 6. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 7. https://t.me/c/3328128766/170 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\170.txt
- 8. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt

## cuba_talks_source

Question: Что в базе говорится о Кубе и переговорах с США?

Profile: `answer`

Note: Cuba talks should be grounded in the direct Cuba posts, not adjacent US/Trump material.

Согласно имеющейся информации, Куба и США провели тайные переговоры в Гаване — это первые прямые контакты за последние 10 лет. Со стороны США во встрече участвовала делегация Госдепартамента, которая встречалась с внуком Рауля Кастро. В ходе переговоров американская сторона предложила снятие торгового эмбарго и доступ к Starlink в обмен на экономические реформы, освобождение политзаключённых и компенсации за конфискованные активы. Также сообщается, что американские чиновники выразили обеспокоенность деятельностью иностранных разведывательных и военных групп на Кубе, приблизившихся к территории США.

На фоне этих переговоров на Кубе продолжаются протесты, сопровождающиеся поджогами отделений...

Sources:
- 1. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
- 2. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 3. https://t.me/c/3841808641/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\6.txt
- 4. https://t.me/c/3841808641/7 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\7.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 7. https://t.me/c/3328128766/142 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\142.txt
- 8. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt

## q9_cuba_protests_source

Question: Что в базе говорится о протестах на Кубе?

Profile: `answer`

Note: Historical Q9 failure: protest answer must prioritize the direct Cuba protests post.

Согласно имеющейся информации, на Кубе продолжаются протесты, которые сопровождаются поджогами. Сообщается, что протестующие поджигают местные отделения Коммунистической партии Кубы в некоторых городах. Одной из причин выхода людей на улицы называется полное отключение электроэнергии, которое длится уже вторую неделю, а также речь президента, объявившего о начале переговоров с США.

В контексте протестов также упоминается энергетическая блокада. Указывается, что Соединенные Штаты блокируют поставки нефти на Кубу с января, а президент США Дональд Трамп подписал указ о введении тарифов против стран, поставляющих нефть Кубе. При этом отмечается, что «другу Владимиру [Путину] можно всё», что на...

Sources:
- 1. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 2. https://t.me/c/3841808641/7 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\7.txt
- 3. https://t.me/c/3328128766/185 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\185.txt
- 4. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 5. https://t.me/c/3299898370/24 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\24.txt
- 6. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 7. https://t.me/c/3328128766/160 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\160.txt
- 8. https://t.me/c/3328128766/16 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\16.txt

## cuba_pressure_deal_source

Question: Как база описывает отношение США к Кубе: давление или попытку сделки?

Profile: `answer`

Note: Pressure-vs-deal wording should be grounded in the direct negotiation/pressure post.

На основании предоставленных данных, политика США по отношению к Кубе описывается как сочетание давления и попытки сделки. Давление проявляется в энергетической блокаде, ограничениях на торговлю нефтью и введении тарифов против стран, поставляющих нефть Кубе. Кроме того, в Сенате США республиканцы заблокировали попытку демократов ограничить полномочия президента на применение военной силы против Кубы без одобрения Конгресса, что указывает на сохранение военного давления.

Одновременно с этим, согласно данным, США и Куба провели тайные переговоры в Гаване — первые за 10 лет. Американская делегация, возглавляемая Госдепартаментом, встречалась с внуком бывшего кубинского лидера Рауля Кастро. В...

Sources:
- 1. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
- 2. https://t.me/c/3841808641/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\6.txt
- 3. https://t.me/c/3841808641/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\9.txt
- 4. https://t.me/c/3841808641/7 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\7.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 7. https://t.me/c/3328128766/188 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\188.txt
- 8. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt

## narva_plans_source

Question: Что в базе говорится о Нарве и планах России против Эстонии?

Profile: `answer`

Note: Narva planning question should ground in the direct Narva/Estonia posts.

В предоставленных материалах обсуждаются различные сценарии, связанные с возможными действиями России в отношении Эстонии, в частности города Нарва. Согласно одному из источников, в социальных сетях появляются аккаунты, продвигающие идею отделения Нарвы и Ида-Вирумаа от Эстонии и создания так называемой «Нарвской народной республики». Автор одного из постов, Александр Нотевский, предполагает, что эти действия могут быть признаком подготовки России к вторжению в Эстонию, однако вопрос о том, насколько серьёзно воспринимается эта угроза, остаётся открытым.

Другие аналитические материалы указывают на то, что российские пропагандисты предлагают захватить Нарву, чтобы «сломать» политическую вол...

Sources:
- 1. https://t.me/c/3889026624/2 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\2.txt
- 2. https://t.me/c/3889026624/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\6.txt
- 3. https://t.me/c/3889026624/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\4.txt
- 4. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 5. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 6. https://t.me/c/3215620297/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\4.txt
- 7. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 8. https://t.me/c/3328128766/196 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\196.txt

## q22_narva_visuals_top_source

Question: Какие кадры или визуалы можно использовать для ролика про Нарву и Эстонию?

Profile: `answer`

Note: Historical Q22 weakness: broad Baltic visuals must not outrank direct Narva/Estonia visual sources.

Для ролика про Нарву и Эстонию можно использовать карту, демонстрирующую потенциальный сценарий российского вторжения в страны Балтии. Хотя эта карта не новая и циркулировала в сети ещё в 2024 году, она визуализирует актуальную тему и может служить сильным иллюстративным материалом. Также подойдут кадры, изображающие гипотетический захват Нарвы: графика, показывающая кинетическую фазу операции — выведение из строя электроснабжения, глушение связи и захват критических узлов, таких как полицейские участки, пограничные пункты и центры местного самоуправления.

В качестве пропагандистского фона можно создать графику, иллюстрирующую «информационное оружие», которое, по данным источников, Россия...

Sources:
- 1. https://t.me/c/3889026624/2 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\2.txt
- 2. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 3. https://t.me/c/3328128766/188 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\188.txt
- 4. https://t.me/c/3328128766/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\4.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/16 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\16.txt
- 7. https://t.me/c/3889026624/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\6.txt
- 8. https://t.me/c/3328128766/187 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\187.txt

## afd_ukraine_stance_source

Question: Что в базе говорится про отношение AfD к войне в Украине?

Profile: `answer`

Note: AfD/Ukraine stance should ground in the direct ultra-left/right topic posts.

Согласно имеющимся данным, избиратели партии AfD демонстрируют решительное неприятие помощи Украине. В частности, опрос Insa, проведённый для BILD, показал, что 65% сторонников AfD и BSW выступают против предоставления любой помощи Украине. Кроме того, сторонники AfD решительно отвергают идею размещения солдат Бундесвера на территории Украины.

Также в источниках упоминается, что издание Politico сообщало об обвинениях в адрес AfD в утечке секретных документов Европейского союза России. Эта информация представлена как заявление источника, а не как установленный факт.

В целом, данные указывают на то, что позиция AfD и её электората по вопросу войны в Украине является последовательно антивое...

Sources:
- 1. https://t.me/c/3299898370/12 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\12.txt
- 2. https://t.me/c/3299898370/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\4.txt
- 3. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 4. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 5. https://t.me/c/3328128766/182 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\182.txt
- 6. https://t.me/c/3215620297/38 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\38.txt
- 7. https://t.me/c/3328128766/30 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\30.txt
- 8. https://t.me/c/3328128766/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\4.txt

## afd_nepotism_source

Question: Где в базе источник про кумовство в AfD? Дай ссылку.

Profile: `source`

Note: Direct AfD nepotism query should resolve to the dedicated AfD nepotism post.

В предоставленной базе данных содержится информация о том, что партия AfD была замешана в скандалах, включая обвинения в кумовстве и преимущественном трудоустройстве родственников как на земельном, так и на федеральном уровне. Конкретный источник, подтверждающий это утверждение, находится в файле `C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\13.txt`. В этом документе анализируются масштабные случаи кумовства в AfD, выходящие за рамки региональной политики Саксонии-Ангальтии и затрагивающие федеральных лидеров партии.

Согласно этому источнику, в Саксонии-Ангальтии основного кандидата земельного отделения AfD Ульриха Зигмунда обвиняют в том,...

Sources:
- 1. https://t.me/c/3299898370/13 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\13.txt
- 2. https://t.me/c/3299898370/12 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\12.txt
- 3. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 4. https://t.me/c/3328128766/170 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\170.txt
- 5. https://t.me/c/3328128766/70 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\70.txt
- 6. https://t.me/c/3299898370/18 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\18.txt
- 7. https://t.me/c/3328128766/97 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\97.txt
- 8. https://t.me/c/3215620297/27 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\27.txt

## north_korea_troops_source

Question: Откуда в базе тезис про северокорейских военных в России? Дай ссылку.

Profile: `source`

Note: North Korea source control keeps the source profile honest on a stable topic.

Тезис о присутствии северокорейских военных в России и их участии в боевых действиях содержится в нескольких документах вашей базы. Основной источник, напрямую описывающий их участие, сообщает, что на январь 2026 года северокорейские войска не просто находятся в тылу, но и непосредственно участвуют в боевых действиях на территории Курской области РФ. Под российским командованием они наносят огневые удары по украинскому приграничью (в частности, Сумской области), используя ствольную артиллерию и реактивные системы залпового огня [2].

Дополнительные источники подтверждают, что северокорейских солдат начали привлекать к нанесению артиллерийских ударов по Украине с российской территории, а так...

Sources:
- 1. https://t.me/c/3215620297/15 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\15.txt
- 2. https://t.me/c/3215620297/13 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\13.txt
- 3. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
