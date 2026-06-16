# Source-Selection Golden Results

Checked at: 2026-06-09T01:08:14+00:00
Query model: `deepseek-v4-flash`
Query base URL: `https://api.deepseek.com`
Mode: `hybrid`
Source limit: `8`
Flags: `RERANKER_ENABLED=False`, `HYBRID_SYNTH_ENABLED=True`, `HYBRID_QUERY_CARDS_ENABLED=True`, `WIKI_ENABLED=True`

Summary: 10/10 passed, avg=100.0, avg_duration=5.463s

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

Да, в предоставленных данных есть информация о том, что Дональд Трамп поддерживал Виктора Орбана. В частности, в одном из источников (Telegram-пост) приводится заявление, приписываемое президенту США, в котором он открыто выражает поддержку венгерскому премьер-министру перед выборами 2026 года, хвалит его политику и призывает граждан Венгрии голосовать за Орбана. В этом же посте утверждается, что Трамп заявляет, будто отношения между США и Венгрией достигли новых высот благодаря Орбану.

Кроме того, в контексте упоминается, что Дональд Трамп-младший также обращался к гражданам Венгрии, а сам Трамп «выражал любовь к Венгрии и хвалил Орбана». В статье Bloomberg отмечается, что ультраправые па...

Sources:
- 1. https://t.me/c/3328128766/148 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\148.txt
- 2. https://t.me/c/3328128766/189 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\189.txt
- 3. https://t.me/c/3328128766/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\8.txt
- 4. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 7. https://t.me/c/3299898370/24 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\24.txt
- 8. https://t.me/c/3328128766/181 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\181.txt

## ultra_left_right_similarity_source

Question: Что в базе говорится о сходстве ультралевых и ультраправых?

Profile: `answer`

Note: The direct similarity claim is canonical in normalized source 11.

В предоставленных данных содержатся утверждения о сходстве ультралевых и ультраправых. В одном из источников говорится, что «ультралевые и ультраправые совпадают», а в другом — что «везде ультралевые и ультраправые одинаковые».

Дополнительные материалы указывают на то, что в некоторых случаях их идеологические установки могут пересекаться. Например, в одном из документов отмечается, что неонацистские группы разрабатывают концепции «белого шариата» и воспевают ИГИЛ и ХАМАС, а также что сеть Terrorgram копирует тактики исламистского терроризма. При этом подчёркивается, что такие идеологические установки, как мизогиния, антисемитизм и антилиберализм, совпадают с джихадистскими.

Также в источ...

Sources:
- 1. https://t.me/c/3299898370/11 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\11.txt
- 2. https://t.me/c/3299898370/22 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\22.txt
- 3. https://t.me/c/3299898370/20 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\20.txt
- 4. https://t.me/c/3328128766/30 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\30.txt
- 5. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 6. https://t.me/c/3328128766/170 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\170.txt
- 7. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 8. https://t.me/c/3328128766/50 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\50.txt

## cuba_talks_source

Question: Что в базе говорится о Кубе и переговорах с США?

Profile: `answer`

Note: Cuba talks should be grounded in the direct Cuba posts, not adjacent US/Trump material.

Согласно имеющейся информации, Куба и США провели тайные переговоры в Гаване — это первые прямые переговоры за последние 10 лет. Со стороны США во встрече участвовала делегация Госдепартамента, которая встречалась с внуком Рауля Кастро. Американская сторона, по данным источников, предложила снятие торгового эмбарго и доступ к Starlink в обмен на экономические реформы, освобождение политзаключённых и компенсации за конфискованные активы. Также сообщается, что американские чиновники выразили обеспокоенность деятельностью иностранных разведывательных и военных групп на Кубе, приблизившихся к территории США.

В то же время на Кубе продолжаются протесты, сопровождающиеся поджогами местных отделе...

Sources:
- 1. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 2. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
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

В контексте протестов упоминается энергетическая блокада: указывается, что Соединенные Штаты блокируют поставки нефти на Кубу с января, а президент США Дональд Трамп подписал указ о введении тарифов против стран, поставляющих нефть Кубе. При этом отмечается, что «другу Владимиру [Путину] можно всё», что намекает...

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

На основании предоставленных данных, политика США по отношению к Кубе описывается как сочетание давления и попытки сделки.

Давление проявляется в энергетической блокаде, ограничениях на торговлю нефтью и введении тарифов против стран, поставляющих нефть Кубе. Кроме того, упоминаются попытки демократов ограничить полномочия президента США на применение военной силы против Кубы без одобрения Конгресса.

Одновременно с этим, согласно источникам, США и Куба провели тайные переговоры в Гаване — первые прямые переговоры за 10 лет. В ходе этих переговоров, по данным источников, США предложили снятие торгового эмбарго и доступ к Starlink в обмен на экономические реформы, освобождение политзаключён...

Sources:
- 1. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
- 2. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 3. https://t.me/c/3841808641/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\6.txt
- 4. https://t.me/c/3841808641/7 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\7.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 7. https://t.me/c/3328128766/188 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\188.txt
- 8. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt

## narva_plans_source

Question: Что в базе говорится о Нарве и планах России против Эстонии?

Profile: `answer`

Note: Narva planning question should ground in the direct Narva/Estonia posts.

Согласно имеющейся информации, в базах данных обсуждаются сценарии, в рамках которых российские пропагандисты предлагают захватить эстонский город Нарва, чтобы «сломать» политическую волю Европы и НАТО. Также рассматривается возможность того, что Россия может попытаться захватить Нарву, постепенно снижая бдительность альянса. Отмечается, что такой шаг потребует не только военных ресурсов, но и подготовки общественного мнения через пропаганду о притеснении русскоязычного населения в Эстонии и Латвии, чтобы создать видимость народного восстания.

В дополнение к этому, в источниках упоминается появление в социальных сетях идей об отделении Нарвы и Ида-Вирумаа от Эстонии с целью создания «Нарвс...

Sources:
- 1. https://t.me/c/3889026624/2 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\2.txt
- 2. https://t.me/c/3889026624/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\6.txt
- 3. https://t.me/c/3889026624/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\9.txt
- 4. https://t.me/c/3889026624/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\4.txt
- 5. https://t.me/c/3299898370/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\9.txt
- 6. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 7. https://t.me/c/3215620297/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\4.txt
- 8. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt

## q22_narva_visuals_top_source

Question: Какие кадры или визуалы можно использовать для ролика про Нарву и Эстонию?

Profile: `answer`

Note: Historical Q22 weakness: broad Baltic visuals must not outrank direct Narva/Estonia visual sources.

Для ролика о Нарве и Эстонии можно использовать следующие визуальные материалы, основанные на предоставленных данных.

**1. Карта и графика сценария вторжения.** Покажите карту, демонстрирующую потенциальный сценарий российского вторжения в страны Балтии. Хотя эта карта не новая и циркулировала в сети ещё в 2024 году, она визуализирует актуальную тему и служит сильным иллюстративным материалом. Дополнительно можно создать графику, изображающую гипотетический захват Нарвы: кинетическую фазу операции с выведением из строя электроснабжения, глушением связи и захватом критических узлов (полицейские участки, пограничные пункты, центры местного самоуправления).

**2. Визуализация пропагандистског...

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

Согласно имеющимся данным, отношение партии AfD к войне в Украине характеризуется последовательным неприятием военной поддержки Киева и акцентом на дипломатическое урегулирование. В частности, опрос Insa, проведённый для BILD, показал, что 65% избирателей AfD и BSW выступают против предоставления любой помощи Украине. Кроме того, сторонники партии решительно отвергают идею размещения солдат Бундесвера в Украине.

Лидер AfD Алиса Вайдель в своих заявлениях подчёркивает необходимость мирного урегулирования конфликта с участием России. Она утверждает, что мир в Европе возможен только с Россией, а не без неё, и что партия всегда выступала за переговоры между Украиной и Россией. Вайдель также во...

Sources:
- 1. https://t.me/c/3299898370/12 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\12.txt
- 2. https://t.me/c/3299898370/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\4.txt
- 3. https://t.me/c/3299898370/15 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\15.txt
- 4. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 5. https://t.me/c/3328128766/162 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\162.txt
- 6. https://t.me/c/3328128766/182 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\182.txt
- 7. https://t.me/c/3215620297/38 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\38.txt
- 8. https://t.me/c/3328128766/30 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\30.txt

## afd_nepotism_source

Question: Где в базе источник про кумовство в AfD? Дай ссылку.

Profile: `source`

Note: Direct AfD nepotism query should resolve to the dedicated AfD nepotism post.

В предоставленной базе данных информация о кумовстве в партии AfD содержится в файле, расположенном по пути: `C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\13.txt`. В этом документе анализируются случаи трудоустройства родственников в структурах партии, включая обвинения в адрес земельного отделения AfD в Саксонии-Ангальтии, где, как утверждается, отец основного кандидата Ульриха Зигмунда получил должность с годовым вознаграждением более 90 тысяч евро. Также упоминается, что сопредседатель партии Тино Хрупалла почти десять лет трудоустраивает жену своего партийного соратника в своём избирательном округе.

Другие предоставленные файлы (наприме...

Sources:
- 1. https://t.me/c/3299898370/13 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\13.txt
- 2. https://t.me/c/3299898370/19 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\19.txt
- 3. https://t.me/c/3299898370/22 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\22.txt
- 4. https://t.me/c/3328128766/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\14.txt
- 5. https://t.me/c/3328128766/170 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\170.txt
- 6. https://t.me/c/3328128766/70 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\70.txt
- 7. https://t.me/c/3299898370/18 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\18.txt
- 8. https://t.me/c/3328128766/97 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\97.txt

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
