# SuperChat — Çoxfunksiyalı köməkçi
Canlı vebsayt (deploy edilmiş versiya): [https://superchat-bot.lovable.app](https://superchat-bot.lovable.app)

SuperChat istifadəçilərə uçuşlar, alış-veriş məhsulları və kino seansları ilə bağlı sorğularında kömək edən çatbot layihəsidir. İstifadəçi gündəlik dildə sorğu yazaraq uyğun uçuşları və məhsulları axtara, filmlər və seanslar haqqında məlumat əldə edə, nəticələri müqayisə edə və mövcud funksiyalardan istifadə edə bilər.

## Əsas imkanlar
- **Uçuş axtarışı:** İstifadəçi gediş və təyinat şəhərlərini, tarixi, aviaşirkəti və qiymət limitini qeyd edərək uyğun uçuşları axtara bilər.
- **Alış-veriş:** Məhsulları adına, brendinə, rənginə və qiymətinə görə axtarmaq, məhsul məlumatlarına baxmaq və uyğun məhsulları müqayisə etmək mümkündür.
- **Kino:** Filmləri janr və dilə görə axtarmaq, kino seansları haqqında məlumat almaq mümkündür.
- **Söhbət konteksti:** Tətbiq əvvəlki sorğuların müəyyən məlumatlarını saxlayaraq istifadəçinin sonrakı dəqiqləşdirici suallarını nəzərə alır.
- **Çoxdilli dəstək:** Layihənin məntiqində Azərbaycan, ingilis və rus dilləri üçün mətnlər nəzərdə tutulub.
- **Şəkil əsasında məhsul axtarışı:** NVIDIA embedding modeli və uyğun embedding məlumatları mövcud olduqda məhsulları yüklənmiş şəkilə əsasən axtarmaq mümkündür.

## Texnologiyalar və alətlər

Layihənin Python hissəsində məlumatların oxunması və emalı, sorğuların uyğun sahəyə yönləndirilməsi və istifadəçi ilə söhbət məntiqi həyata keçirilir. Məhsul şəkilləri üzrə vizual axtarış üçün `NumPy` və NVIDIA API-si ilə uyğun işləyən `OpenAI` Python kitabxanasından istifadə olunur.

### Layihənin hazırlanmasında istifadə olunan alətlər

Layihənin hazırlanması boyunca aşağıdakı alətlərdən istifadə etmişəm:

- **Gemini AI:** Layihənin əsas kodlarının yaradılması və ilkin proqramlaşdırma işləri üçün əsas alət kimi istifadə olunub.
- **Claude AI:** Kodlar icra edilərkən yaranan xətaların araşdırılması və aradan qaldırılması üçün istifadə olunub.
- **Visual Studio Code (VS Code):** Kod fayllarının və qovluqlarının yaradılması, redaktəsi və kodların icrası üçün istifadə olunub.

## Məlumat mənbələri

Layihədə üç əsas məlumat sahəsi üzrə məlumatlardan istifadə olunur:

### Kino məlumatları

Kino məlumatları kino sahəsi ilə əlaqəli API vasitəsilə əldə edilib. Əldə edilən məlumatlar layihədə emal edilərək film və seans axtarışında istifadə edilir.

### Alış-veriş məlumatları

Məhsul məlumatları **Birmarket** mənbəyindən scrape edilərək əldə olunub. Məhsullar üzrə vizual axtarış imkanının işləməsi üçün **NVIDIA API açarından** (`NVIDIA_API_KEY`) istifadə edilir. Bu funksiya üçün `data/product_embeddings.json` faylında uyğun embedding məlumatlarının da olması tələb olunur.

### Aviabilet məlumatları (Aviasales)

Uçuş məlumatları **Travelpayouts** platformasının [Data API](https://app.travelpayouts.com/all_tools) alətləri və Travelpayouts API tokeni vasitəsilə əldə edilib (`data/aviasales.json`).

**API token necə yaradılır:**

1. [Travelpayouts](https://app.travelpayouts.com/all_tools) platformasında hesab yaradın.
2. Hesabınıza daxil olub **Data API** kateqoriyasına keçin.
3. Profil səhifəsindən API token yaradın: [Travelpayouts API Token](https://app.travelpayouts.com/profile/api-token).

> **Xəbərdarlıq:** API açarlarını və tokenləri açıq GitHub repository-sinə yerləşdirməyin. Onları kompüterinizdə mühit dəyişəni kimi saxlayın.

## Layihənin qovluq strukturu

Repository-də əsas Python faylları və məlumat qovluqları aşağıdakı məqsədlərə xidmət edir:

```text
ctrlishers_assessment2/
├── app.py          # Tətbiqin əsas giriş nöqtəsi və interaktiv terminal rejimi
├── domains.py      # Uçuş, alış-veriş və kino sahələrinin əməliyyat məntiqi
├── repositories.py # JSON məlumatlarının oxunması və axtarış əməliyyatları
├── router.py       # İstifadəçi sorğularının təhlili və uyğun sahəyə yönləndirilməsi
├── state.py        # Söhbət vəziyyətinin və əvvəlki nəticələrin saxlanması
├── data/           # API-lərdən əldə edilmiş real məlumatlar və embedding faylları
├── mock/           # Nümunə məlumatları olan JSON faylları
├── scrape/         # Məlumatların əldə edilməsi ilə bağlı skriptlər
└── probe_out/      # Yoxlama və ya analiz nəticələri üçün fayllar
```

Tətbiq başladıqda `mock/` qovluğundakı uçuş, məhsul, film, kino və seans JSON fayllarını oxuyur. `data/` qovluğunda uyğun real məlumat faylları mövcud olduqda onları da əsas məlumat dəstinə əlavə edir.

## Quraşdırılma və işə salınma

### 1. Tələblər

Kompüterinizdə aşağıdakı proqramların quraşdırıldığına əmin olun:

- Python 3.10 və ya daha yeni versiya
- Git
- Visual Studio Code (istəyə bağlıdır)

### 2. Repository-ni kompüterə köçürün

```bash
git clone https://github.com/gazizovaa/ctrlishers_assessment2.git
cd ctrlishers_assessment2
```

### 3. Lazımi Python paketlərini quraşdırın

```bash
python -m pip install --upgrade pip
python -m pip install numpy openai
```

### 4. Məlumat fayllarını yoxlayın

Proqramın düzgün başlaması üçün `mock/` qovluğunda aşağıdakı JSON faylları olmalıdır:

- `flights.json`
- `products.json`
- `movies.json`
- `cinemas.json`
- `showtimes.json`

Real məlumatlardan istifadə etmək üçün uyğun fayllar `data/` qovluğunda yerləşdirilməlidir:

- `aviasales.json`
- `birmarket.json`
- `cinemaplus.json`
- `films_row.json`

Şəkil əsasında məhsul axtarışını aktivləşdirmək üçün `data/product_embeddings.json` faylı və NVIDIA API açarı tələb olunur. Bu funksiya lazım deyilsə, NVIDIA API açarı olmadan da mətn əsaslı funksiyalardan istifadə edə bilərsiniz.

### 5. API açarını konfiqurasiya edin (istəyə bağlı)

Şəkil əsasında məhsul axtarışından istifadə edəcəksinizsə, NVIDIA API açarını mühit dəyişəni kimi təyin edin.

**Windows PowerShell:**

```powershell
$env:NVIDIA_API_KEY="sizin_nvidia_api_acariniz"
```

### 6. Tətbiqi bir komanda ilə başladın

Paketlər quraşdırıldıqdan və tələb olunan JSON faylları mövcud olduqdan sonra layihənin əsas qovluğunda bu əmri icra edin:

```bash
python app.py
```

Proqram başladıqda terminalda `SuperChat ready. Type 'exit' to quit.` mesajı görünəcək. Bundan sonra sorğularınızı daxil edə bilərsiniz. Proqramdan çıxmaq üçün `exit` və ya `quit` yazın.

Nümunə sorğular:

```text
Find me a flight from Baku to Istanbul.
Show me laptops under 1000 AZN.
What is playing tonight?
```

**Qeyd:** Repository-dəki `app.py` faylı hazırda terminal üzərindən işləyən interaktiv Python tətbiqini başladır. Yuxarıda göstərilən [canlı vebsayt](https://superchat-bot.lovable.app) isə ayrıca yayımlanmış (deploy edilmiş) veb interfeysidir. `python app.py` əmri həmin vebsaytı lokal serverdə açmır; repository-dəki Python tətbiqini terminalda işə salır.

## Demo rejimi

Tətbiqin əvvəlcədən hazırlanmış nümunə söhbətlərini yoxlamaq üçün əsas qovluqda aşağıdakı əmri icra edə bilərsiniz:

```bash
python app.py --demo
```

## Təhlükəsizlik qeydi

NVIDIA API açarı və Travelpayouts API tokeni kimi məxfi məlumatları ictimai repository-də paylaşmayın. Bu məlumatları mühit dəyişənlərində və ya Git tərəfindən izlənməyən lokal konfiqurasiya faylında saxlayın.
