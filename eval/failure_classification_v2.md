# Failure classification (dev, RRF rank > 50)

Per item, write ONE category after CAT: (letter), optionally a note.
  E = embedding/semantic miss: the passage answers it, but meaning was not matched
  V = vocabulary mismatch: answers it, but question and passage share almost no words
  C = chunking: the answer is split across chunks or buried in a long chunk
  L = label problem: the labelled passage does not really answer the question
  Q = question problem: question too vague / ambiguous to retrieve anything specific
  O = other (say what)

Items: 14

## F01  rank 21 (dense 65, bm25 11)  [lexical]
QUESTION: What did Secretary of State Frank B. Kellogg recommend to President Coolidge in June 1926 regarding the 1919 Paris Convention, in connection with the Greco-Bulgarian incident (Petrich)?

LABELLED PASSAGE ([FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]): Accordingly, I would recommend that, if this course meets with your approval, the Senate be requested to take suitable action advising and consenting to the ratification of the International Convention Relating to the Regulation of Aerial Navigation with Articles 5 and 34 amended as proposed, upon the conditions and understandings outlined in the following suggested resolution to be made a part of the instrument of ratification:

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]
579.6 D 1/221a The Secretary of State to President Coolidge Washington , June 15, 1926 . The President : The undersigned the Secretary of State has the honor to lay before the President, with a view to its transmission to the Senate to receive the advice and consent of that body to its ratification, if his judgment approve

CAT: 

## F02  rank 21 (dense 19, bm25 88)  [lexical]
QUESTION: Why was the conference to resolve the territory's fate in the partition of Upper Silesia (Germany-Poland) repeatedly delayed through mid-1921?

LABELLED PASSAGE ([Commons, 1921-06-09, "UPPEE SILESIA.", Mr. CHAMBERLAIN]): I think it is because other parties to the conference are not ready.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-06-09, "UPPEE SILESIA.", Colonel WEDGWOOD]
What is it that is obstructing or delaying the meeting of the conference to decide the settlement of Upper Silesia?

CAT: 

## F03  rank 22 (dense 127, bm25 15)  [semantic]
QUESTION: Why did the local legislature insist on a condition protecting its territorial rights before approving the treaty with the mandatory power regarding the Mosul question (Turkey-Iraq frontier)?

LABELLED PASSAGE ([Commons, 1924-07-14, "ANGLO-IRAQ TREATY.", Mr. THOMAS]): The Assembly attached a rider in the following terms to its acceptance of the Treaty: 19 This treaty and its subsidiary agreements shall become null and void if the British Government fail to safeguard the rights of Iraq in the Mosul vilayet in their entirety.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. THURTLE]
Hon. Members opposite must accept a good deal of responsibility for it, because our Government was partly responsible for seducing these Syrians from their real allegiance and making them take part in a fight against the Turkish Government, which was really over them. There is a point about the legality of the position taken up by the Turkis

CAT: 

## F04  rank 27 (dense 94, bm25 16)  [semantic]
QUESTION: What happened when the bilateral negotiations between the two governments over the Mosul question (Turkey-Iraq frontier) failed to produce an agreement before the deadline?

LABELLED PASSAGE ([Commons, 1924-10-08, "TURCO-IRAQ FRONTIER.", The UNDER-SECRETARY of STATE for FOREIGN AFFAIRS (Mr. Ponsonby)]): The question of the Turco-Iraq frontier was referred to the Council of the League of Nations in accordance with Article 3 (2) of the Treaty of Lausanne. As a result, it has beers agreed at Geneva that the Council will delimit the frontier between Turkey and Iraq, and both the Turkish and British delegates have given undertakings that their respective Governments will accept any decision which the Council may adopt and will meanwhile maintain and respect the status quo, that is to say, the position as it stood at the time of the conclusion of the Treaty of Lausanne.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1924-06-17, "IRAQ (TURKISH FRONTIER CONFERENCE).", Mr. PONSONBY]
By Article 3 of the Treaty, the frontier between Turkey and Iraq will be laid down in friendly agreement to be concluded betwen Turkey and Great Britain within nine months. In the event of no agreement being reached between the two Governments within the 1948 time mentioned, the dispute will be referred to the Council of th

CAT: 

## F05  rank 48 (dense 79, bm25 83)  [lexical]
QUESTION: Why was the conference to resolve the territory's fate in the partition of Upper Silesia (Germany-Poland) repeatedly delayed through mid-1921?

LABELLED PASSAGE ([Commons, 1921-06-09, "UPPEE SILESIA.", Mr. CHAMBERLAIN]): His Majesty's Government are ready for a conference at an early date, but the arrangements have not yet been made.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1921-06-09, "UPPEE SILESIA.", Colonel WEDGWOOD]
What is it that is obstructing or delaying the meeting of the conference to decide the settlement of Upper Silesia?

CAT: 

## F06  rank 66 (dense 97, bm25 140)  [multi-doc]
QUESTION: Who were the three members of the committee established in September 1920 to propose a final settlement of the Aaland Islands question, and which countries did they represent?

LABELLED PASSAGE ([FRUS frus1920v01, 1920-11, "The Ambassador in France ( Wallace ) to the Secretary of State"]): Other members of the Commission were Baron Beyens of Belgium, Maggiorino Ferraris of Italy, and Felix Calonder of Switzerland.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1920v01, 1920-07, "The Ambassador in Great Britain ( Davis ) to the Secretary of State"]
758.6114AI/84: Telegram The Ambassador in Great Britain ( Davis ) to the Secretary of State London , July 14, 1920—3 p.m. [Received 3:22 p.m.] 1062. The Council of the League of Nations now in session in London has unanimously adopted the following resolution, the representatives of Finland and Swede

CAT: 

## F07  rank 68 (dense 91, bm25 80)  [semantic]
QUESTION: Who was responsible for bringing the two parties back together after the Council's decision to finalize a lasting agreement on the Mosul question (Turkey-Iraq frontier)?

LABELLED PASSAGE ([Commons, 1926-04-19, "MOSUL FRONTIER.", Sir A. CHAMBERLAIN]): His Majesty's Ambassador left Constantinople on the 16th April for Angora, where he will resume negotiations with the Turkish Minister for Foreign Affairs.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1925-04-08, "MOSUL FRONTIER.", Marquess of HARTINGTON]
asked the Secretary of State for Foreign Affairs when the Council of the League of Nations is expected to take its decision regarding the Mosul frontier; whether the British representative at the thirteenth session of the League of Nations Council gave a definite undertaking that the British Government would abide by the Council's de

CAT: 

## F08  rank 78 (dense 157, bm25 94)  [semantic]
QUESTION: Which articles of the aviation convention did Kellogg propose amending, in connection with the Greco-Bulgarian incident (Petrich)?

LABELLED PASSAGE ([FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]): the International Convention Relating to the Regulation of Aerial Navigation with Articles 5 and 34 amended as recommended by the International Commission for Air Navigation in the protocols of amendment approved by the Commission on October 27, 1922 and June 30, 1923, respectively.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]
The Secretary of State has very properly called attention to provisions of Articles 34 and 37 having to do with the League of Nations and the Permanent Court of International Justice, respectively, and has indicated how these provisions, and certain other provisions of the convention to which this Government would not be i

CAT: 

## F09  rank 175 (dense 349, bm25 140)  [why]
QUESTION: How quickly did the League act when fighting broke out on the Greek-Bulgarian border, and why did it work?

LABELLED PASSAGE ([Lords, 1925-11-25, "LEAGUE OF NATIONS.", VISCOUNT CECIL OF CHELWOOD]): it is worth observing that in the Græco-Bulgarian dispute, which has just taken place, you first stop the fighting, you first require each country to withdraw its troops from the other country, and then arbitration follows as a matter of course.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-07-14, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
Now I come to the case of Greece. Here I think I can claim that the British Government and the British people have done good work. Mr. Morgenthau, the American head of the Committee dealing with Greek refugees, came here some time in April and it fell to my lot to be Chairman of the Sub-Committee which deals with this question 

CAT: 

## F10  rank 573 (dense 425, bm25 759)  [multi-doc]
QUESTION: Why did critics in parliament suspect that economic resources, rather than humanitarian or legal obligations, explained the government's Iraq policy?

LABELLED PASSAGE ([Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. WALLHEAD]): According to the report of the right hon. Member for Norwich: If oil is found in sufficient quantity in Mosul there will be a pipe line right to the Mediterranean. 9.0 P.M. We shall continue our experiments, no doubt, until we find out whether it is a paying proposition or not. If it does not pay, we shall come out, and leave the Arabs to themselves. If it does pay, we shall find it in consonance with honour, affinity, and obligations to remain there, world without end.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Commons, 1926-02-18, "ANGLO-IRAQ TREATY.", Mr. AMERY]
Much more recently, barely 30 years ago, not only members of the Opposition, but supporters of the Government of the day, derided the project of the Uganda Railway as a ludicrous waste of money, and even those who defended it advocated it, not on the strength of its economic possibilities, but on the strength of our missionary obligations and 

CAT: 

## F11  rank 605 (dense 587, bm25 593)  [semantic]
QUESTION: When did Bulgaria accede to the base Convention and its Additional Protocol, and how does this timing compare to Greece's ratification?

LABELLED PASSAGE ([FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]): Bulgaria July 5, 1923 France Oct. 13, 1919 June 1, 1922 Greece do do

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [FRUS frus1926v01, 1926-06, "The Secretary of State to President Coolidge"]
13, 1919 Peru June 22, 1920 * The Convention has been denounced by Bolivia with effect as from the 30th August 1924. Note : The dates in tabulation are those given by the International Commission for Air Navigation The Department of State is informed that Chile has decided to adhere to the convention. Names of States Addit

CAT: 

## F12  rank 1816 (dense 1937, bm25 1270)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1920-06-28, "AALAND ISLANDS.", The PRIME MINISTER]): As stated by hon. Friend the Under-Secretary of State for Foreign Affairs on the 23rd June, in reply to a question by my hon. Friend the Member for Lincoln, the Secretary of State, acting in exercise of the friendly right conferred by Article XI. of the Covenant of the League of Nations, has brought to the attention of the Council of the League the case of the Aaland Islands as a matter affecting international relations, which unfortunately threatens to disturb the good understanding between nations upon whom peace depends. He has informed the Governments of Sweden and Finland of the action which he felt it his duty to take, and both Governments have expressed their satisfaction that the case will now be examined without delay.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: 

## F13  rank 2158 (dense 2020, bm25 1945)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1922-03-27, "VILNA.", The UNDER-SECRETARY of STATE for FOREIGN AFFAIRS (Mr. Cecil Harmsworth)]): An act of union drawn up by the Polish Government, including a Clause for the creation of a statute for Vilna, received on 22nd March the signatures of the 12 Vilna delegates who had hitherto opposed it. This is thought to be equivalent to the acceptance by the Vilna diet of the act which will now presumably be ratified. The answer to the second part of the question is in the affirmative, both countries having replied.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: 

## F14  rank 2661 (dense 2788, bm25 2540)  [cross-case]
QUESTION: Which disputes did the League of Nations manage to settle in the early 1920s?

LABELLED PASSAGE ([Commons, 1924-10-08, "TURCO-IRAQ FRONTIER.", The UNDER-SECRETARY of STATE for FOREIGN AFFAIRS (Mr. Ponsonby)]): The question of the Turco-Iraq frontier was referred to the Council of the League of Nations in accordance with Article 3 (2) of the Treaty of Lausanne. As a result, it has beers agreed at Geneva that the Council will delimit the frontier between Turkey and Iraq, and both the Turkish and British delegates have given undertakings that their respective Governments will accept any decision which the Council may adopt and will meanwhile maintain and respect the status quo, that is to say, the position as it stood at the time of the conclusion of the Treaty of Lausanne.

PASSAGE SPLIT ACROSS CHUNKS: no

TOP-1 RETRIEVED INSTEAD: [Lords, 1924-04-02, "COUNCIL OF THE LEAGUE OF NATIONS.", LORD PARMOOR]
It has become a permanent thing to bring into operation a system for deciding international disputes and international friction, taking the place of the mere arbitrament of war. I do not want for the moment, nor is it necessary, to dwell at any special length upon that aspect of the case, but surely it is satisfactory to find t

CAT: 
