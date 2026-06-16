# Source-Selection Golden Results

Checked at: 2026-06-12T14:17:05+00:00
Query model: `deepseek-v4-flash`
Query base URL: `https://api.deepseek.com`
Mode: `hybrid`
Source limit: `8`
Flags: `RERANKER_ENABLED=False`, `HYBRID_SYNTH_ENABLED=True`, `HYBRID_QUERY_CARDS_ENABLED=True`, `WIKI_ENABLED=True`

Summary: 10/10 passed, avg=100.0, avg_duration=5.761s

| Case | Score | Pass | Rank | Missing | Top-forbidden |
|---|---:|:---:|---:|---|---|
| f1_trump_orban_source | 100 | Y | 1 | - | - |
| ultra_left_right_similarity_source | 100 | Y | 1 | - | - |
| cuba_talks_source | 100 | Y | 1 | - | - |
| q9_cuba_protests_source | 100 | Y | 1 | - | - |
| cuba_pressure_deal_source | 100 | Y | 1 | - | - |
| narva_plans_source | 100 | Y | 1 | - | - |
| q22_narva_visuals_top_source | 100 | Y | 1 | - | - |
| afd_ukraine_stance_source | 100 | Y | 2 | - | - |
| afd_nepotism_source | 100 | Y | 1 | - | - |
| north_korea_troops_source | 100 | Y | 1 | - | - |

## f1_trump_orban_source

Question: Трамп реально поддерживал Орбана? Дай источник.

Profile: `source`

Note: Historical F1 source-grounding case: support for Orban should resolve to direct Hungary/Slovakia posts.

Да, в предоставленном контексте есть информация о том, что Дональд Трамп поддерживал Виктора Орбана. В одном из источников содержится заявление от имени президента США Дональда Трампа, в котором он открыто поддерживает венгерского премьер-министра Виктора Орбана перед выборами 2026 года, хвалит его политику и призывает венгров голосовать за него. В этом же посте утверждается, что Трамп заявляет, что отношения между США и Венгрией достигли новых высот благодаря Орбану.

Однако важно отметить, что эта информация представлена как утверждение источника, а не как установленный факт. Автор поста также саркастически комментирует это заявление, предполагая, что такая поддержка может быть концом как...

Sources:
- 1. https://t.me/c/3328128766/148 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\148.txt

## ultra_left_right_similarity_source

Question: Что в базе говорится о сходстве ультралевых и ультраправых?

Profile: `answer`

Note: The direct similarity claim is canonical in normalized source 11.

В предоставленном контексте указывается, что ультралевые и ультраправые могут совпадать в своих целях и тактиках, несмотря на идеологическую противоположность. В частности, отмечается, что «ультралевые и ультраправые совпадают», а также приводятся примеры, когда обе эти силы объединяются в своей ненависти к общим политическим фигурам, таким как председатель Европейской комиссии Урсула фон дер Ляйен. Её политика вызывает критику как со стороны ультраправых (за либерализм в миграции и экологии), так и со стороны ультралевых (за милитаризацию ЕС и поддержку Израиля), что демонстрирует пересечение их оппозиционных позиций.

Кроме того, контекст описывает симбиоз неонацистских и джихадистских ид...

Sources:
- 1. https://t.me/c/3299898370/11 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\11.txt
- 2. https://t.me/c/3299898370/22 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\22.txt
- 3. https://t.me/c/3299898370/20 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\20.txt
- 4. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt
- 5. https://t.me/c/3328128766/111 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\111.txt
- 6. https://t.me/c/3328128766/123 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\123.txt
- 7. https://t.me/c/3328128766/135 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\135.txt
- 8. https://t.me/c/3328128766/136 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\136.txt

## cuba_talks_source

Question: Что в базе говорится о Кубе и переговорах с США?

Profile: `answer`

Note: Cuba talks should be grounded in the direct Cuba posts, not adjacent US/Trump material.

Согласно имеющейся информации, на Кубе на фоне экономического кризиса и полного отключения электричества, которое длится уже вторую неделю, продолжаются протесты. Сообщается, что протестующие поджигают местные отделения Коммунистической партии Кубы. Дополнительным поводом для недовольства стало заявление президента Кубы о начале переговоров с США.

В контексте упоминается, что США и Куба провели тайные переговоры в Гаване — первые прямые переговоры за 10 лет. По данным источника, делегация Госдепартамента США встречалась с внуком Рауля Кастро. В ходе этих переговоров США якобы предложили снятие торгового эмбарго и доступ к Starlink в обмен на экономические реформы, освобождение политзаключё...

Sources:
- 1. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 2. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
- 3. https://t.me/c/3841808641/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\6.txt
- 4. https://t.me/c/3328128766/133 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\133.txt
- 5. https://t.me/c/3328128766/148 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\148.txt
- 6. https://t.me/c/3328128766/150 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\150.txt
- 7. https://t.me/c/3328128766/163 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\163.txt
- 8. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt

## q9_cuba_protests_source

Question: Что в базе говорится о протестах на Кубе?

Profile: `answer`

Note: Historical Q9 failure: protest answer must prioritize the direct Cuba protests post.

Согласно имеющейся информации, на Кубе продолжаются протесты, вызванные глубоким экономическим кризисом. Ситуация усугубляется полным отключением электричества, которое длится уже вторую неделю. Дополнительным поводом для недовольства стало заявление президента Кубы о начале переговоров с США.

Источники сообщают, что протестующие поджигают местные отделения Коммунистической партии Кубы. Таким образом, протесты сопровождаются актами поджогов и происходят на фоне масштабного блэкаута.

Sources:
- 1. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 2. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt
- 3. https://t.me/c/3328128766/111 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\111.txt
- 4. https://t.me/c/3328128766/123 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\123.txt
- 5. https://t.me/c/3328128766/135 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\135.txt
- 6. https://t.me/c/3328128766/136 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\136.txt
- 7. https://t.me/c/3328128766/163 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\163.txt
- 8. https://t.me/c/3328128766/133 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\133.txt

## cuba_pressure_deal_source

Question: Как база описывает отношение США к Кубе: давление или попытку сделки?

Profile: `answer`

Note: Pressure-vs-deal wording should be grounded in the direct negotiation/pressure post.

Согласно предоставленному контексту, отношение США к Кубе описывается как попытка сделки, а не исключительно как давление. В контексте упоминаются тайные переговоры в Гаване, которые стали первыми прямыми переговорами за 10 лет. В ходе этих переговоров США предложили снятие торгового эмбарго и доступ к Starlink в обмен на экономические реформы, освобождение политзаключённых и компенсации за конфискованные активы. Это указывает на попытку заключения взаимовыгодного соглашения.

В то же время, контекст содержит элементы, которые можно интерпретировать как давление. Например, американские чиновники выразили обеспокоенность деятельностью иностранных разведывательных и военных групп на Кубе, при...

Sources:
- 1. https://t.me/c/3841808641/8 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\8.txt
- 2. https://t.me/c/3841808641/5 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\5.txt
- 3. https://t.me/c/3841808641/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Куба\6.txt
- 4. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt
- 5. https://t.me/c/3328128766/102 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\102.txt
- 6. https://t.me/c/3328128766/109 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\109.txt
- 7. https://t.me/c/3328128766/110 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\110.txt
- 8. https://t.me/c/3328128766/133 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\133.txt

## narva_plans_source

Question: Что в базе говорится о Нарве и планах России против Эстонии?

Profile: `answer`

Note: Narva planning question should ground in the direct Narva/Estonia posts.

В предоставленном контексте обсуждаются гипотетические сценарии, связанные с Нарвой и возможными действиями России против Эстонии. В частности, отмечается появление в социальных сетях идей об отделении Нарвы и Ида-Вирумаа от Эстонии с целью создания «Нарвской народной республики». Автор одного из материалов, Александр Нотевский, высказывает предположение, что такие действия могут быть признаком подготовки России к вторжению в Эстонию, однако это остаётся его оценкой, а не установленным фактом.

Аналитики, в том числе из Гарварда, предупреждают о высокой вероятности ограниченного российского вторжения в страны Балтии, особенно при благоприятном для Москвы завершении войны в Украине. В рамках...

Sources:
- 1. https://t.me/c/3889026624/2 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\2.txt
- 2. https://t.me/c/3889026624/6 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\6.txt
- 3. https://t.me/c/3889026624/9 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\9.txt
- 4. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt
- 5. https://t.me/c/3328128766/111 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\111.txt
- 6. https://t.me/c/3328128766/123 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\123.txt
- 7. https://t.me/c/3328128766/135 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\135.txt
- 8. https://t.me/c/3328128766/136 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\136.txt

## q22_narva_visuals_top_source

Question: Какие кадры или визуалы можно использовать для ролика про Нарву и Эстонию?

Profile: `answer`

Note: Historical Q22 weakness: broad Baltic visuals must not outrank direct Narva/Estonia visual sources.

Для ролика про Нарву и Эстонию можно использовать визуальные кадры, отражающие ключевые локации и атмосферу региона. Начните с панорамных видов Нарвы: замок Германа на фоне реки Нарвы, мост Дружбы, соединяющий Эстонию и Россию, а также виды на Ивангородскую крепость с эстонской стороны. Эти кадры подчеркнут пограничное положение города и его историческое значение. Также включите сцены повседневной жизни в Нарве — улицы, местные рынки или промышленные зоны Ида-Вирумаа, чтобы показать контраст между историей и современностью.

Для передачи контекста обсуждений в социальных сетях можно использовать анимированные графики или скриншоты постов с хештегами, связанными с «Нарвской народной республи...

Sources:
- 1. https://t.me/c/3889026624/2 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Балтийские страны\2.txt

## afd_ukraine_stance_source

Question: Что в базе говорится про отношение AfD к войне в Украине?

Profile: `answer`

Note: AfD/Ukraine stance should ground in the direct ultra-left/right topic posts.

Согласно имеющейся информации, немецкая ультраправая партия «Альтернатива для Германии» (АдГ) подозревается в передаче секретных данных Европейского Союза России. Как утверждает источник Politico, эти подозрения касаются передачи информации, которая включает данные о местной противодроновой обороне, западных поставках оружия Украине, а также об осведомлённости властей о российской диверсионной деятельности в Балтийском море.

Кроме того, в контексте упоминается, что среди сторонников правых партий в Германии, к которым относится и AfD, значительная часть выступает против усиления поддержки Украины. Это подтверждается данными опроса Insa для BILD, который показал разобщённость немецкого обще...

Sources:
- 1. https://t.me/c/3299898370/19 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\19.txt
- 2. https://t.me/c/3299898370/12 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\12.txt
- 3. https://t.me/c/3299898370/4 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\4.txt
- 4. https://t.me/c/3328128766/100 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\100.txt
- 5. https://t.me/c/3328128766/111 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\111.txt
- 6. https://t.me/c/3328128766/123 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\123.txt
- 7. https://t.me/c/3328128766/135 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\135.txt
- 8. https://t.me/c/3328128766/136 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\136.txt

## afd_nepotism_source

Question: Где в базе источник про кумовство в AfD? Дай ссылку.

Profile: `source`

Note: Direct AfD nepotism query should resolve to the dedicated AfD nepotism post.

В предоставленном контексте информация о кумовстве в партии AfD содержится в файле **13.txt** из папки «Ультра левые и ультра правые». В этом документе анализируются случаи трудоустройства родственников, выходящие за рамки региональной политики Саксонии-Ангальтии и затрагивающие федеральных лидеров партии. В частности, согласно утверждению источника, основного кандидата земельного отделения AfD Ульриха Зигмунда обвиняют в том, что его отец получил должность в парламентской среде партии с годовым вознаграждением более 90 тысяч евро. Также утверждается, что сопредседатель AfD Тино Хрупалла уже почти десять лет трудоустраивает жену своего партийного соратника в своём избирательном округе в Сак...

Sources:
- 1. https://t.me/c/3299898370/13 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\13.txt
- 2. https://t.me/c/3299898370/19 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\19.txt
- 3. https://t.me/c/3299898370/22 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Ультра левые и ультра правые\22.txt
- 4. https://t.me/c/3328128766/133 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\133.txt
- 5. https://t.me/c/3328128766/148 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\148.txt
- 6. https://t.me/c/3328128766/150 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\150.txt
- 7. https://t.me/c/3328128766/163 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\163.txt
- 8. https://t.me/c/3328128766/129 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Венгрия Словакия\129.txt

## north_korea_troops_source

Question: Откуда в базе тезис про северокорейских военных в России? Дай ссылку.

Profile: `source`

Note: North Korea source control keeps the source profile honest on a stable topic.

Тезис о присутствии северокорейских военных в России основан на заявлениях официальных лиц и данных разведок, которые приводятся в предоставленных источниках. В частности, в одном из документов содержится утверждение министра обороны Японии о том, что более 10 000 северокорейских солдат были направлены в Россию и проходят обучение передовым методам ведения войны, включая использование дронов, искусственного интеллекта и киберопераций. Этот тезис не является установленным фактом, а воспроизводится как заявление источника.

Дополнительно, согласно данным украинской разведки, опубликованным в Wall Street Journal, северокорейские солдаты привлекаются Россией к боевым действиям на Украине, включ...

Sources:
- 1. https://t.me/c/3215620297/15 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\15.txt
- 2. https://t.me/c/3215620297/13 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\13.txt
- 3. https://t.me/c/3215620297/14 | C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\normalized\Корея\14.txt
