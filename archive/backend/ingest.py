from sqlalchemy.orm import Session
from database import engine
from models import Document

try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    _model = None

def chunk_text(text, size=500, overlap=50):
    """
    Splits the input text into chunks of specified size with optional overlap.

    Args:
        text (str): The input text to be chunked.
        size (int): The maximum size of each chunk.
        overlap (int): The number of overlapping characters between chunks.

    Returns:
        list: A list of text chunks.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start += size - overlap  # Move the start index forward with overlap
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    if _model is None:
        return [[0.0] * 384 for _ in texts]
    return _model.encode(texts).tolist()



def main():
    # example usage of chunk_text and embed functions
    text = "World War I or the First World War (28 July 1914-11 November 1918), also known as the Great War, was a global conflict between two coalitions: the Allies (or Entente) and the Central Powers. Major theatres of war included Europe and the Middle East, and well as parts of Africa and the Asia-Pacific. One of the deadliest conflicts in history, World War I resulted in an estimated 15 to 22 million deaths, including in mass war crimes against civilians and genocides. The conflict saw important developments in weaponry, including the first large-scale use of machine guns, artillery, aircraft, chemical weapons, and tanks, and was a major factor in the deadly Spanish flu pandemic.\nThe causes of World War I included the rise of the German Empire, which disturbed the long-standing balance of power in Europe, and the exacerbation of imperial rivalries, as reflected in new alliances and an arms race between the great powers. Tensions in the Balkans reached a breaking point on 28 June 1914 when Gavrilo Princip, a Bosnian Serb, assassinated Franz Ferdinand, the heir to the Austro-Hungarian throne. Austria-Hungary blamed Serbia and declared war on 28 July, upon which the Russian Empire mobilised in Serbia's defence. In early August, Germany declared war on Russia and France; the United Kingdom entered the war after Germany invaded Belgium. Germany's strategy in 1914 was to quickly defeat France, but its advance was halted in September, and the Western Front solidified into a near-continuous line of fortified trenches from the English Channel to Switzerland. The Eastern Front was more dynamic, but neither side gained a decisive advantage, despite costly offensives. The Ottoman Empire joined the Central Powers in November, which was followed by a failed Allied campaign at Gallipoli. Japan and Italy also joined the Allies.\nMajor battles, including those at Verdun, the Somme, and Passchendaele, failed to break the stalemate on the Western Front. In April 1917, the United States joined the Allies after Germany resumed unrestricted submarine warfare against Atlantic shipping. Later that year, the Bolsheviks seized power in Russia in the October Revolution; Soviet Russia signed an armistice with the Central Powers in December, followed by a separate peace in March 1918. That month, Germany launched a spring offensive in the west, which despite initial successes left the German Army exhausted and demoralised. The Allied Hundred Days Offensive, beginning in August 1918, caused a collapse of the German front line. By early November, the Allies had signed armistices with the Ottomans and with Austria-Hungary, leaving Germany isolated. Facing a revolution at home, Kaiser Wilhelm II abdicated on 9 November, and the war ended with the Armistice of 11 November 1918.\nThe Paris Peace Conference of 1919-1920 imposed settlements on the defeated powers. Under the Treaty of Versailles, Germany lost significant territories, was disarmed, and was required to pay large war reparations to the Allies. The collapse of the Russian, German, Austro-Hungarian, and Ottoman empires resulted in new national boundaries and the creation of new independent states including Poland, Finland, the Baltic states, Czechoslovakia, and Yugoslavia. The League of Nations was established to maintain world peace, but its failure to manage instability during the interwar period contributed to the outbreak of World War II in 1939." 

    chunks = chunk_text(text, size=500, overlap=50)
    embeddings = embed(chunks)

    # Insert into documents table and print how many chunks inserted
    with Session(engine) as session:
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc = Document(text=chunk, embedding=embedding, source="wikipedia:WW1")
            session.add(doc)
        session.commit()
        print(f"Inserted {len(chunks)} chunks into the documents table.")

if __name__ == "__main__":
    main()

