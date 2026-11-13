# Failure classification (dev, RRF rank > 50)

Per item, write ONE category after CAT: (letter), optionally a note.
  E = embedding/semantic miss: the passage answers it, but meaning was not matched
  V = vocabulary mismatch: answers it, but question and passage share almost no words
  C = chunking: the answer is split across chunks or buried in a long chunk
  L = label problem: the labelled passage does not really answer the question
  Q = question problem: question too vague / ambiguous to retrieve anything specific
  O = other (say what)

Items: 25

## F01  rank 55 (dense 11, bm25 923)  [multi-doc]
QUESTION: What frontier line did the League Commission recommend, and did the Permanent Court of International Justice confirm the Council's authority to decide the matter?

LABELLED PASSAGE ([Lords, 1925-12-21, "LEAGUE OF NATIONS.", THE CHANCELLOR OF THE DUCHY OF LANCASTER (VISCOUNT CECIL OF CHELWOOD)]): The decision of the Council was, as the noble and learned Lord has said, to uphold as the boundary—subject, of course, to delimitation—the broad line laid down at the suggestion of Mr. Branting at the Council to which the noble and learned Lord has referred.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1925-11-16, "NORTHERN FRONTIER.", Mr. AMERY]
The question of the northern frontier of Iraq has been before the Council of the League of Nations, which, as the hon. Member is probably aware, referred certain judicial points to the Permanent Court of International Justice at The Hague. The Permanent Court has not yet given a decision on the points referred to it, but it is hoped that the d

CAT: L (Jasper: passage answers neither part; top-1 Amery chunk is closer) [Jasper, overrides Hermes F]

## F02  rank 66 (dense 97, bm25 140)  [multi-doc]
QUESTION: Who were the three members of the committee established in September 1920 to propose a final settlement of the Aaland Islands question, and which countries did they represent?

LABELLED PASSAGE ([FRUS frus1920v01, 1920-11, "The Ambassador in France ( Wallace ) to the Secretary of State"]): Other members of the Commission were Baron Beyens of Belgium, Maggiorino Ferraris of Italy, and Felix Calonder of Switzerland.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1920v01, 1920-07, "The Ambassador in Great Britain ( Davis ) to the Secretary of State"]
758.6114AI/84: Telegram The Ambassador in Great Britain ( Davis ) to the Secretary of State London , July 14, 1920—3 p.m. [Received 3:22 p.m.] 1062. The Council of the League of Nations now in session in London has unanimously adopted the following resolution, the representatives of Finland and Swede

CAT: V (Commission vs committee; names only) [Hermes]

## F03  rank 71 (dense 86, bm25 116)  [follow-up]
QUESTION (history: Why were Allied troops stationed in Upper Silesia?): What was the cost of that, and who paid?

LABELLED PASSAGE ([Commons, 1922-06-29, "ARMY OF OCCUPATION (RHINE AND SILESIA).", Lieut.-Colonel STANLEY]): The cost of the British Army of Occupation on the Rhine and in Silesia for the period 1st April to 30th June, 1922, is estimated at £600,000.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-11-10, "LEAGUE OF NATIONS (BUDGET).", Sir C. KINLOCH-COOKE]
asked the Chancellor of the Exchequer whether he is now in a position to give the cost to the State of the last British delegation to the League of Nations at Geneva; what is the estimated cost of the League for 1921–22; what share is to be paid by Great Britain and what share by the other members of the League; can he say 

CAT: Q (follow-up retrieved without history) [Hermes]

## F04  rank 104 (dense 1477, bm25 47)  [multi-doc]
QUESTION: How did the League of Nations' approach to resolving the Vilna dispute change between the 1921 plebiscite discussions and the final 1923 decision?

LABELLED PASSAGE ([Commons, 1921-06-01, "LITHUANIA.", Mr. CHAMBERLAIN (Leader of the House)]): Monsieur Hymans has been delegated by the League of Nations to preside over conferences between Polish and Lithuanian delegates in Brussels, and will submit any solution that may be reached to the Council of the League of Nations for its decision.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-03-01, "PLEBISCITE, VILNA.", Mr. W. CARTER]
asked the Prime Minister whether he can make any statement as to the situation in Vilna; and what progress the League of Nations is making with arrangements for the plebiscite in that area?

CAT: L (one step of a multi-step answer) [Hermes]

## F05  rank 106 (dense 40, bm25 2605)  [multi-doc]
QUESTION: Why did critics in parliament suspect that economic resources, rather than humanitarian or legal obligations, explained the government's Iraq policy?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. GRIFFITHS]): It is said that Mosul has nothing whatever to do with oil. I want to ask one question. Assume for a moment that Mosul was a cabbage patch. Would you be there? You would not be there at all.

PASSAGE SPLIT ACROSS CHUNKS: yes

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. AMERY]
Much more recently, barely 30 years ago, not only members of the Opposition, but supporters of the Government of the day, derided the project of the Uganda Railway as a ludicrous waste of money, and even those who defended it advocated it, not on the strength of its economic possibilities, but on the strength of our missionary obligations and 

CAT: C (passage split across chunks; also no word oil) [Hermes]

## F06  rank 149 (dense 212, bm25 147)  [follow-up]
QUESTION (history: Why were Allied troops stationed in Upper Silesia?): What was the cost of that, and who paid?

LABELLED PASSAGE ([Commons, 1922-03-20, "BRITISH TEOOPS, SILESIA.", Mr. HARMSWORTH]): The cost is chargeable to Poland and Germany under the terms of the Treaty of Versailles.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-11-10, "LEAGUE OF NATIONS (BUDGET).", Sir C. KINLOCH-COOKE]
asked the Chancellor of the Exchequer whether he is now in a position to give the cost to the State of the last British delegation to the League of Nations at Geneva; what is the estimated cost of the League for 1921–22; what share is to be paid by Great Britain and what share by the other members of the League; can he say 

CAT: Q (follow-up without history) [Hermes]

## F07  rank 164 (dense 199, bm25 176)  [follow-up]
QUESTION (history: What was the Vilna dispute?): Why did the League fail there?

LABELLED PASSAGE ([Commons, 1923-03-19, "VILNA.", Mr. McNEILL]): No, Sir; it is not correct to say that it was handed over to the League of Nations. The League of Nations were informally asked if they would devise conditions and submit them to the parties interested. They did so, and the parties, as a matter of fact, rejected those terms; consequently, the responsibility for a decision was thrown back upon the Allied and Associated Powers.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-03-23, "LEAGUE OF NATIONS.", Mr. MacDONALD]
He was perfectly justified in saying that, provided he brought it off. He has not done so. It has resulted in the most lamentable failure that British diplomacy has had to face for a great many years. It is not merely a question of failure. Nobody can pull off things always, but when one fails, one can fail with the consciousness that he d

CAT: Q (follow-up without history) [Hermes]

## F08  rank 175 (dense 349, bm25 140)  [why]
QUESTION: How quickly did the League act when fighting broke out on the Greek-Bulgarian border, and why did it work?

LABELLED PASSAGE ([Lords, 1925-11-25, "LEAGUE OF NATIONS.", VISCOUNT CECIL OF CHELWOOD]): it is worth observing that in the Græco-Bulgarian dispute, which has just taken place, you first stop the fighting, you first require each country to withdraw its troops from the other country, and then arbitration follows as a matter of course. I believe that to be, I will not say the only way in which arbitration will be established, but the normal, usual and healthy way in which it will be established.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-07-14, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
Now I come to the case of Greece. Here I think I can claim that the British Government and the British people have done good work. Mr. Morgenthau, the American head of the Committee dealing with Greek refugees, came here some time in April and it fell to my lot to be Chairman of the Sub-Committee which deals with this question 

CAT: V (Graeco-Bulgarian spelling with ae ligature) [Hermes]

## F09  rank 178 (dense 82, bm25 1268)  [multi-doc]
QUESTION: Why did critics in parliament suspect that economic resources, rather than humanitarian or legal obligations, explained the government's Iraq policy?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. PURCELL]): It is pretty clear, as far as we are able to judge, that oil is at the bottom of the question, and, as I say, we would have heard nothing about Mosul if it had not been for these oil sinkages.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. AMERY]
Much more recently, barely 30 years ago, not only members of the Opposition, but supporters of the Government of the day, derided the project of the Uganda Railway as a ludicrous waste of money, and even those who defended it advocated it, not on the strength of its economic possibilities, but on the strength of our missionary obligations and 

CAT: V (economic resources vs oil) [Hermes]

## F10  rank 224 (dense 1676, bm25 108)  [semantic]
QUESTION: Why did the local legislature insist on a condition protecting its territorial rights before approving the treaty with the mandatory power?

LABELLED PASSAGE ([Commons, 1924-07-14, "ANGLO-IRAQ TREATY.", Mr. THOMAS]): The Assembly attached a rider in the following terms to its acceptance of the Treaty: 19 This treaty and its subsidiary agreements shall become null and void if the British Government fail to safeguard the rights of Iraq in the Mosul vilayet in their entirety.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-04-20, "TREATY OF PEACE (HUNGARY) BILL", Lord R. CECIL]
I hope the recommendation of the Brussels Conference will not be lost sight of, and that it will be a condition of any assistance given to any of these States that they should cease, to waste their money in useless military preparation. There is no greater criticism of the Supreme Council and of its work at Paris than that they

CAT: V (paraphrased by design: local legislature, mandatory power) [Hermes]

## F11  rank 292 (dense 1449, bm25 150)  [multi-doc]
QUESTION: How did Viscount Cecil defend the December 1925 Council decision in the Lords?

LABELLED PASSAGE ([Lords, 1925-12-21, "LEAGUE OF NATIONS.", VISCOUNT CECIL OF CHELWOOD]): I cannot help feeling that a policy of abandonment of that kind would, in the existing circumstances and after everything that has occurred, be a serious blow to our reputation and one that would have a repercussion in other countries far removed from Mesopotamia.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", VISCOUNT CECIL OF CHELWOOD]
He only made a reservation as to one of them

CAT: L (one arbitrary sentence from a long defence) [Hermes]

## F12  rank 333 (dense 437, bm25 283)  [lexical]
QUESTION: Why was the conference to resolve the territory's fate repeatedly delayed through mid-1921?

LABELLED PASSAGE ([Commons, 1921-06-09, "UPPEE SILESIA.", Mr. CHAMBERLAIN]): I think it is because other parties to the conference are not ready.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1922-03-27, "FOREIGN AFFAIRS.", Captain ELLIOT]
The plebiscite was held, and the people of that district gave a decided majority in favour of restoration to the kingdom of Hungary. At present a determination is going on of the frontier of Transylvania between the kingdoms of Hungary and Rumania, and I beg to the Under-Secretary to make some attempt to see that the principles under which 

CAT: Q (does not name the case) [Hermes]

## F13  rank 504 (dense 5784, bm25 235)  [follow-up]
QUESTION (history: What was the Mosul dispute about?): Did Britain accept the League's decision?

LABELLED PASSAGE ([Commons, 1925-04-08, "MOSUL FRONTIER.", Mr. CHAMBERLAIN]): The answers to the three remaining parts of the question are in the affirmative.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. AMERY]
I must correct my right how Friend. When that Commission reported there had been no League of Nations decision, so, obviously, Turkey could not have refused to accept. The position was this, that the Turkish representative at Geneva had promised in advance to accept the decision of the League, whatever it might be, and it was on the strength o

CAT: L (passage meaningless alone) [Hermes]

## F14  rank 605 (dense 587, bm25 593)  [semantic]
QUESTION: When did Bulgaria accede to the base Convention and its Additional Protocol, and how does this timing compare to Greece's ratification?

LABELLED PASSAGE ([FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]): Bulgaria July 5, 1923 France Oct. 13, 1919 June 1, 1922 Greece do do

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]
13, 1919 Peru June 22, 1920 * The Convention has been denounced by Bolivia with effect as from the 30th August 1924. Note : The dates in tabulation are those given by the International Commission for Air Navigation The Department of State is informed that Chile has decided to adhere to the convention. Names of States Addit

CAT: C (table row chunked) [Hermes]

## F15  rank 870 (dense 588, bm25 1651)  [follow-up]
QUESTION (history: Why were Allied troops stationed in Upper Silesia?): What was the cost of that, and who paid?

LABELLED PASSAGE ([Commons, 1922-03-20, "BRITISH TEOOPS, SILESIA.", Colonel WEDGWOOD]): What is the use of charging this to Germany when she is not paying the bill?

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-11-10, "LEAGUE OF NATIONS (BUDGET).", Sir C. KINLOCH-COOKE]
asked the Chancellor of the Exchequer whether he is now in a position to give the cost to the State of the last British delegation to the League of Nations at Geneva; what is the estimated cost of the League for 1921–22; what share is to be paid by Great Britain and what share by the other members of the League; can he say 

CAT: L (does not answer the question) [Hermes]

## F16  rank 963 (dense 492, bm25 3196)  [semantic]
QUESTION: What was the economic motivation behind the rejected 1925 proposal to divide the disputed territory?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Sir A. CHAMBERLAIN]): What was the basis of the proposition? It was that Turkey should have so much as she desired of the vilayet of Mosul. That was one side of the bargain. The other side was that a British company, approved by His Majesty's Government, should have the exploitation of all the oil.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1925-03-05, "FOREIGN AFFAIRS.", Mr. FISHER]
We are opposed for two very good reasons. In the first place, in the early part of 1922, a defensive pact was offered by the Government of my right hon. Friend the Member for Carnarvon Boroughs to Belgium and France as part of a general arrangement in which Russia was to be included "for the appeasement" of Europe, but that offer was summarily 

CAT: E (answers it, meaning not matched) [Hermes]

## F17  rank 1293 (dense 4819, bm25 637)  [semantic]
QUESTION: What happened when the bilateral negotiations between the two governments failed to produce an agreement before the deadline?

LABELLED PASSAGE ([Commons, 1924-10-08, "TURCO-IRAQ FRONTIER.", The UNDER-SECRETARY of STATE for FOREIGN AFFAIRS (Mr. Ponsonby)]): The question of the Turco-Iraq frontier was referred to the Council of the League of Nations in accordance with Article 3 (2) of the Treaty of Lausanne. As a result, it has beers agreed at Geneva that the Council will delimit the frontier between Turkey and Iraq... The Council has resolved to set up a Committee of three persons to advise it.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1924-07-14, "FOREIGN OFFICE.", The PRIME MINISTER]
That matter has been referred to legal experts. There it will remain until the reports conic before the Inter-Allied Conference this week or next. This is the simple fact that remains quite evident; it was absolutely essential, after the publication of the Dawes Report, that negotiations between the countries should be preceded by conver

CAT: Q (does not name the case) [Hermes]

## F18  rank 1556 (dense 2626, bm25 828)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1921-06-01, "LITHUANIA.", Mr. CHAMBERLAIN (Leader of the House)]): There is no tribunal in Brussels, as suggested. Monsieur Hymans has been delegated by the League of Nations to preside over conferences between Polish and Lithuanian delegates in Brussels, and will submit any solution that may be reached to the Council of the League of Nations for its decision.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: L (shows a referral, not a settlement) [Hermes]

## F19  rank 1816 (dense 1937, bm25 1270)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1920-06-28, "AALAND ISLANDS.", The PRIME MINISTER]): As stated by hon. Friend the Under-Secretary of State for Foreign Affairs on the 23rd June, in reply to a question by my hon. Friend the Member for Lincoln, the Secretary of State, acting in exercise of the friendly right conferred by Article XI. of the Covenant of the League of Nations, has brought to the attention of the Council of the League the case of the Aaland Islands as a matter affecting international relations, which unfortunately threatens to disturb the good understanding between nations upon whom peace depends. He has informed the Governments of Sweden and Finland of the action which he felt it his duty to take, and both Governments have expressed their satisfaction that the case will now be examined without delay.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: L (referral, not a settlement) [Hermes]

## F20  rank 1987 (dense 4792, bm25 976)  [follow-up]
QUESTION (history: What was the Vilna dispute?): Why did the League fail there?

LABELLED PASSAGE ([Commons, 1920-11-22, "LITHUANIA (POLISH ADVANCE).", The PRIME MINISTER]): According to our latest information, General Seligowski, who has been publicly disowned by the Polish Government, is continuing his attacks against the Lithuanians, the League of Nations Commission having not yet succeeded in arranging an armistice.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-03-23, "LEAGUE OF NATIONS.", Mr. MacDONALD]
He was perfectly justified in saying that, provided he brought it off. He has not done so. It has resulted in the most lamentable failure that British diplomacy has had to face for a great many years. It is not merely a question of failure. Nobody can pull off things always, but when one fails, one can fail with the consciousness that he d

CAT: Q (follow-up without history) [Hermes]

## F21  rank 2294 (dense 1239, bm25 4270)  [follow-up]
QUESTION (history: Tell me about the Mosul question after Lausanne.): What did the government decide about the treaty?

LABELLED PASSAGE ([Commons, 1926-06-21, "MOSUL BOUNDARY TREATY (RATIFICATION).", The SECRETARY of STATE for FOREIGN AFFAIRS (Sir Austen Chamberlain)]): Both the Turkish National Assembly and the Iraq Parliament have authorised the ratification of the Treaty forthwith; it is eminently desirable that the British ratification should be given at the earliest possible moment. Unless, therefore, the right hon. Gentleman desires a discussion on the Treaty in this House, His Majesty will be advised to ratify in a few days.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1925-03-11, "FOREIGN AFFAIRS (PARLIAMENTARY CONTROL).", Mr. TREVELYAN]
In the case of important. Treaties, the Government will, of course, take the opportunity of submitting them to the House for discussion within this period. But, as the Government cannot take upon itself to decide what may be considered important or unimportant, if there is a formal demand for discussion forwarded thro

CAT: Q (follow-up without history) [Hermes]

## F22  rank 2661 (dense 2788, bm25 2540)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1924-10-08, "TURCO-IRAQ FRONTIER.", The UNDER-SECRETARY of STATE for FOREIGN AFFAIRS (Mr. Ponsonby)]): The question of the Turco-Iraq frontier was referred to the Council of the League of Nations in accordance with Article 3 (2) of the Treaty of Lausanne. As a result, it has beers agreed at Geneva that the Council will delimit the frontier between Turkey and Iraq, and both the Turkish and British delegates have given undertakings that their respective Governments will accept any decision which the Council may adopt and will meanwhile maintain and respect the status quo, that is to say, the position as it stood at the time of the conclusion of the Treaty of Lausanne.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: L (referral, not a settlement) [Hermes]

## F23  rank 3384 (dense 2203, bm25 4243)  [cross-case]
QUESTION: How did Parliament react when the League's decisions went against British wishes?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. AMERY]): That is not the view which the League of Nations took of it.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-03-23, "LEAGUE OF NATIONS.", Mr. THURTLE]
They quail before the monocle of the Foreign Secretary. The reason why I believe we are going into the Lobby against the Government this evening may be put briefly in a few words. We contend that the Foreign Secretary misled the House of Commons and the people of this country, and we contend that when he got to Geneva he failed to carry out 

CAT: L (does not answer) [Hermes]

## F24  rank 4896 (dense 6764, bm25 3092)  [semantic]
QUESTION: Who was responsible for bringing the two parties back together after the Council's decision to finalize a lasting agreement?

LABELLED PASSAGE ([Commons, 1926-04-19, "MOSUL FRONTIER.", Sir A. CHAMBERLAIN]): His Majesty's Ambassador left Constantinople on the 16th April for Angora, where he will resume negotiations with the Turkish Minister for Foreign Affairs.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1925-12-21, "LEAGUE OF NATIONS.", VISCOUNT CECIL OF CHELWOOD]
If they have pressed for a decision by the Council, it is only because they believed that until the Council had pronounced upon the question submitted to it by the Treaty of Lausanne, it was impossible to find a common basis on which to found the discussion of an agreement with the Turkish Government. The British Government most

CAT: Q (does not name the case) [Hermes]

## F25  rank 5745 (dense 3661, bm25 7307)  [cross-case]
QUESTION: How did Parliament react when the League's decisions went against British wishes?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. MacDONALD]): The right hon. Gentleman knows quite well that the Report of the Commission, which was the material for consideration at Geneva was one of those extraordinary Reports which, if the weight of it had been taken altogether, would have been in favour of Mosul going away from Iraq, historical evidence etc.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-03-23, "LEAGUE OF NATIONS.", Mr. THURTLE]
They quail before the monocle of the Foreign Secretary. The reason why I believe we are going into the Lobby against the Government this evening may be put briefly in a few words. We contend that the Foreign Secretary misled the House of Commons and the people of this country, and we contend that when he got to Geneva he failed to carry out 

CAT: L (partial at best) [Hermes; Jasper: Q]
