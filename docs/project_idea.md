Pipeline może codziennie pobierać dane źródłowe, normalizować je do wspólnego schematu, liczyć pola pochodne nq\_qqq\_ratio i vvix\_vix\_ratio, a następnie zapisywać wynik do BigQuery oraz tabeli błędów. To świetnie pasuje do wcześniejszego pomysłu, bo możesz pokazać walidację schematu, np. brak kolumny close, niepoprawny ticker, duplikat daty lub dzielenie przez zero przy VIX, oraz zwracać czytelne komunikaty zamiast surowych wyjątków.



Cel projektu

Zbuduj pipeline, który pobiera dane z zewnętrznego API, normalizuje je w Pythonie, waliduje strukturę rekordu i zapisuje wynik do BigQuery, a w razie problemów zapisuje czytelne błędy do logów oraz osobnej tabeli błędów. Dzięki temu pokazujesz dwie rzeczy naraz: implementację funkcji w środowisku cloud oraz poprawę komunikatów błędów dla użytkownika lub operatora systemu.



Temat danych:



Cena QQQ, NQM26, VIX, VVIX (dane rynkowe).


Uzasadnienie biznesowe:
Ratio VVIX/VIX ma sens analityczny, bo łączy poziom oczekiwanej zmienności rynku akcji z „volatility of volatility”, czyli napięciem w samym rynku opcyjnym; taki sygnał można traktować jako filtr reżimu ryzyka. Ratio NQM26/QQQ też ma uzasadnienie, bo zestawia futures na Nasdaq z ETF-em śledzącym podobny segment rynku i może służyć do monitorowania rozjazdów cenowych, jakości danych albo prostych alertów anomalii, ale do portfolio lepiej opisać to jako narzędzie monitoringu relacji instrumentów niż gotową strategię tradingową



Architektura

Najprostsza wersja: harmonogram uruchamia skrypt Bash, ten wywołuje moduł Pythona, a aplikacja pobiera dane, waliduje rekordy, zapisuje poprawne do BigQuery i loguje błędy do Cloud Logging lub do pliku lokalnego w wersji demo. W drugiej iteracji możesz przenieść uruchamianie do Cloud Run Jobs albo Cloud Functions, bo to lepiej pokazuje praktyczne użycie GCP.



Minimalne komponenty:



extract.py — pobranie danych z API.



transform.py — mapowanie pól i normalizacja typów.



validate.py — walidacja schematu i reguł biznesowych.



load.py — zapis do BigQuery.



errors.py — własne wyjątki i komunikaty dla użytkownika.



run\_pipeline.sh — skrypt uruchamiający cały przepływ.



tests/ — testy jednostkowe i regresyjne.



.github/workflows/ci.yml — testy i lint przed wdrożeniem.



Funkcje MVP

Najważniejsze jest, żeby każda zmiana w danych była „change-safe”: gdy dodasz nowe pole, pipeline powinien wykryć, czy schema mapping, walidacja i testy zostały zaktualizowane, zamiast po cichu przepuścić błędne dane. To bardzo dobrze odwzorowuje zadania typu rozwijanie pól i funkcji oraz pilnowanie, żeby nowe zmiany nie psuły istniejących zachowań.



W MVP zrób:



Pobieranie danych z jednego endpointu i zapis do jednej tabeli.



Jawny model rekordu, np. event\_id, source, timestamp, value, status.



Walidację pól obowiązkowych, typów i zakresów wartości.



Przyjazne błędy, np. „brakuje pola timestamp”, „value musi być liczbą”, „rekord odrzucony: nieznany status”.



Tryb --dry-run, który wykonuje walidację bez zapisu do bazy.



Plik .env.example oraz konfigurację przez zmienne środowiskowe.



Testy i jakość

Ta oferta mocno akcentuje testy regresyjne, więc w projekcie pokaż, że po każdej zmianie uruchamiasz testy jednostkowe, integracyjne i zestaw przypadków „historycznych”, które wcześniej działały poprawnie. Dobrze też pokazać, że komunikaty błędów są testowane tak samo jak logika, bo poprawa error messaging jest jednym z obowiązków.



Przykładowe testy:



test\_transform\_valid\_record — poprawne mapowanie danych wejściowych.



test\_missing\_required\_field — czy komunikat błędu jasno wskazuje brakujące pole.



test\_invalid\_type\_for\_value — czy zły typ nie przechodzi walidacji.



test\_schema\_change\_requires\_mapping\_update — regresja po dodaniu nowego pola.



test\_bigquery\_payload\_shape — czy rekord ma właściwy format przed loadem.



test\_cli\_dry\_run — czy pipeline kończy się poprawnie bez zapisu.



Sierra Chart ma wbudowane mechanizmy eksportu danych intraday do tekstu/CSV oraz study, które potrafi zapisywać bar data i wartości studiów do pliku i aktualizować go na bieżąco. To oznacza, że możesz potraktować Sierra jako źródło danych, a własny pipeline jako warstwę ETL odpowiedzialną za parsing, deduplikację, liczenie ratio i zapis do PostgreSQL lub BigQuery.



Najbardziej sensowny przepływ:



Sierra Chart zapisuje dane do pliku .txt lub .csv.



Python wykrywa zmianę pliku albo odpala się co minutę z crona/Task Scheduler.

​



Skrypt ładuje tylko nowe wiersze, normalizuje timestamp i symbole.

​



Dane trafiają do tabel raw\_prices, potem do derived\_metrics.

​Z kolei Cboe jawnie publikuje historyczne dane VIX i VVIX, więc dla części volatility masz bardzo dobrą podstawę do legalnego i prostego zasilania pipeline’u.



Dwa warianty

Wariant prostszy: użyj Write Bar and Study Data To File, bo ten study zapisuje do pliku dane OHLCV oraz wartości studiów i aktualizuje plik w czasie rzeczywistym, gdy pojawiają się nowe bary. To jest bardzo dobre, jeśli chcesz eksportować nie tylko cenę, ale też własne wskaźniki albo np. przygotowane w Sierra wartości pomocnicze.

​



Wariant bardziej „surowy”: użyj eksportu intraday data do text file, gdzie Sierra zapisuje rekordy w formacie Date, Time, Open, High, Low, Last, Volume, NumberOfTrades, BidVolume, AskVolume, a timestamp w takim eksporcie jest w UTC. Ten wariant jest lepszy, jeśli chcesz mieć pełną kontrolę nad własnym przetwarzaniem i samemu liczyć wszystko po stronie Pythona.

​



Jak zasilać bazę

Najwygodniej zrób mały loader w Pythonie, który działa inkrementalnie: trzyma last\_processed\_timestamp albo hash ostatniego wiersza i przy każdym uruchomieniu dopisuje tylko nowe rekordy. Dzięki temu nie musisz za każdym razem importować całego pliku, a projekt od razu wygląda bardziej „production-like”, bo pokazuje idempotencję, deduplikację i odporność na restart.



Przykładowy flow:



export/SC\_NQ\_bar\_data.txt



export/SC\_QQQ\_bar\_data.txt



export/SC\_VIX\_bar\_data.txt



export/SC\_VVIX\_bar\_data.txt



python ingest.py --source sierra\_files



zapis do raw\_market\_data



job SQL/Python liczący nq\_qqq\_ratio i vvix\_vix\_ratio



Do bazy najlepiej zapisuj:



symbol



bar\_timestamp\_utc



open



high



low



close/last



volume



source\_file



ingested\_at



Co pokazać w projekcie

To jest mocne portfolio, jeśli dodasz walidację jakości danych: brakujące kolumny, nieuporządkowane timestampy, duplikaty, puste wolumeny, zerowy VIX przy liczeniu ratio i mismatch stref czasowych. Sierra podaje, że eksport intraday ma określony format pól, a przy eksporcie intraday timestamp jest w UTC, podczas gdy Write Bar and Study Data To File zapisuje czas zgodny z time zone chartu, więc to świetny punkt do pokazania świadomej normalizacji czasu w pipeline.



Przykładowe komunikaty błędów:



Missing required column: AskVolume



Timestamp order violation for symbol NQM26



Division by zero: VIX close equals 0



Duplicate bar detected for QQQ at 2026-03-19 14:30:00 UTC



Najlepsza architektura

Dla portfolio polecałbym układ:



Sierra Chart eksportuje pliki.



Python watcher/ingestor czyta nowe dane.

​



PostgreSQL trzyma surowe i przeliczone rekordy.



Osobny moduł liczy NQM26/QQQ i VVIX/VIX.



GitHub Actions odpala testy parsera, walidacji i regresji na przykładowych plikach.



Opcjonalnie BigQuery albo GCS dodajesz jako „cloud extension”, jeśli chcesz mocniej zbliżyć projekt do opisu stanowiska.

​



W Twoim przypadku szczególnie sensowne jest połączenie Sierra Chart + PostgreSQL jako wersji lokalnej oraz dodatkowego eksportu do Google Cloud jako wersji „deployment/demo”, bo wtedy projekt łączy Twoje realne dane tradingowe z wymaganiami stanowiska



Jak to zbudować

Pipeline może codziennie pobierać dane źródłowe, normalizować je do wspólnego schematu, liczyć pola pochodne nq\_qqq\_ratio i vvix\_vix\_ratio, a następnie zapisywać wynik do BigQuery oraz tabeli błędów. To świetnie pasuje do wcześniejszego pomysłu, bo możesz pokazać walidację schematu, np. brak kolumny close, niepoprawny ticker, duplikat daty lub dzielenie przez zero przy VIX, oraz zwracać czytelne komunikaty zamiast surowych wyjątków.



Przykładowe encje:



raw\_prices — data, symbol, close, source, load\_timestamp.

​



derived\_metrics — data, qqq\_close, vix\_close, vvix\_close, vvix\_vix\_ratio, nq\_close, nq\_qqq\_ratio.



pipeline\_errors — stage, symbol, error\_code, user\_message, technical\_details.



