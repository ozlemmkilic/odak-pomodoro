# Odak 2.2 — Microsoft Store yayın rehberi

Bu klasör güncellenmiş uygulama kaynaklarını, MSIX derleme sistemini,
ikonları, tanıtım önizlemelerini ve Store metinlerini içerir. Henüz
Microsoft Store'a yüklenmiş veya Microsoft tarafından onaylanmış değildir.
Hazır Windows EXE/MSIX içermez; aşağıdaki komutlar Windows'ta üretir.

## 1. Geliştirici hesabını ve uygulama adını oluştur

1. https://storedeveloper.microsoft.com adresini kendi tarayıcında aç.
2. Bireysel yayınlayacaksan **Individual developer / Get started for free**
   seçeneğiyle ilerle. Microsoft'un güncel belgesine göre yeni bireysel
   kayıt akışı ücretsizdir. Şirket hesabının koşulları farklıdır.
3. Microsoft hesabınla oturum açıp Microsoft'un kimlik doğrulamasını tamamla.
   Şifreni, doğrulama kodunu veya kimlik belgeni bu proje klasörüne koyma.
4. Partner Center'da **Apps and games → New product → MSIX or PWA app**
   seç. İstediğin uygulama adını rezerve et. `Odak` adının müsait olduğu
   varsayılmıyor; seçtiğin müsait ad kullanılacak.
5. Ürün sayfasında **Product management → Product identity** bölümünden
   `Package/Identity/Name`, `Package/Identity/Publisher` ve
   `Package/Properties/PublisherDisplayName` değerlerini aynen kopyala.
   `DisplayName` için rezerve ettiğin uygulama adını kullan.

Bu değerler paket kimliğidir; şifre değildir. Kişisel görevler ve geçmiş
paylaşılmaz. Mağazada görünmesini istediğin yayıncı adını ve herkese açık
destek e-postasını sen seçmelisin. Geliştirici hesabının yasal doğrulaması
Microsoft'un kendi ekranlarında tamamlanır.

## 2. Gizlilik sayfasını yayımla

`store/privacy.html` uygulamanın veri davranışını açıklayan hazır sayfadır.
Yayıncı iletişim bilgilerini ekleyip kendi HTTPS sitene yükleyebilirsin.
Siten yoksa GitHub Pages gibi statik sayfa barındıran bir hizmette yalnızca
bu HTML dosyası için bir site açabilirsin. Örneğin GitHub'da bir depo oluştur,
dosyayı `index.html` olarak yükle, **Settings → Pages → Deploy from a branch**
ile ana dalı ve kök klasörü seç. Hizmetin verdiği HTTPS adresini kullan.
Özel uygulama kaynaklarını, veritabanını veya kimlik belgelerini yükleme.

Adresi gizli sekmede aç: giriş istemeden okunmalı. Bu adresi derleyicinin
`PrivacyUrl` alanına ve Partner Center'ın **Privacy policy URL** alanına gir.
Derlemeden çıkan `privacy.html` yayıncı/destek bilgilerini de içerir;
son başvurudan önce yayımladığın sayfayı o dosyayla güncelle.

## 3. Windows bilgisayarını bir kez hazırla

- Windows 10 sürüm 2004/build 19041 veya üzeri ya da Windows 11, x64.
- https://www.python.org/downloads/windows/ üzerinden **Python 3.13 x64**.
- https://developer.microsoft.com/windows/downloads/windows-sdk/ üzerinden
  **Windows SDK**. `MakeAppx.exe` / MSIX paketleme araçları ve
  **Windows App Certification Kit** bileşenlerini kur. Visual Studio şart değil.
- ZIP'i tamamen çıkart. ZIP içinden çalıştırma. Dosya yolu yazılabilir olsun.

Uygulamanın kurulumdan sonra Python'a ihtiyacı olmaz. Python yalnızca
geliştiricinin derlemesi içindir. Kullanıcı uygulamayı Store'dan açar.

## 4. Paketi oluştur

`STORE_HAZIRLA.bat` dosyasına çift tıkla. İlk çalışmada şu alanları ister:

| Alan | Girilecek değer |
|---|---|
| IdentityName | Partner Center `Package/Identity/Name` |
| Publisher | Partner Center `Package/Identity/Publisher`, `CN=...` dahil |
| PublisherDisplayName | Partner Center'daki yayıncı görünen adı |
| DisplayName | Rezerve ettiğin ürün adı |
| SupportEmail | Kullanıcılara açık destek adresi |
| PrivacyUrl | Yayımlanmış gizlilik sayfasının HTTPS adresi |

Değerler yalnızca `store/store-config.json` içine yazılır. Elle düzenlemek
istersen örnek JSON'u bu adla kopyalayabilirsin. JSON'a yorum ekleme.

Derleyici bağımlılıkları PyPI'dan, LGPL kaynaklarını Qt'nin resmî
sunucularından indirir; Qt kaynaklarında SHA-256 doğrular. Testleri çalıştırır,
ayrı DLL'ler içeren uygulamayı ve MSIX paketini üretir. Yönetici yetkisi,
sertifika kurma veya güvenlik ayarlarını kapatma işlemi yapmaz.
Mevcut bir `release` çıktısının üzerine yazmaz; eski çıktıyı taşımalısın.

Çıktılar:

```text
release/2.2.0.0-store/
  OdakPomodoro_2.2.0.0_x64.msix
  OdakPomodoro/OdakPomodoro.exe
  OdakPomodoro/AppxManifest.xml
  screenshots/
  privacy.html
  build-dependencies.txt
  SHA256SUMS.json
```

MSIX bu aşamada imzasızdır. Store'a gönderilen MSIX için ayrıca ticari
kod imzalama sertifikası satın almak gerekmiyor; Microsoft onaydan sonra
paketi imzalar. İmzasız MSIX'e çift tıklayarak normal kurulum yapılamaması
beklenir. Dosyanın adını EXE yapma, Windows güvenliğini kapatma.

Kaynaklar `source-cache` klasöründe saklanır. Qt/PySide6 LGPL koşulları için
bu klasörü, kullanılan derleme bağımlılıklarını ve kaynak sürümünü koru.
Paketindeki `SOURCE_OFFER.txt`, destek adresinden karşılık gelen kütüphane
kaynaklarını sağlama taahhüdüdür. En az belirtilen süre boyunca talepleri
karşılayabilmelisin. Uygulama kaynakları ve yeniden derleme tarifi de
kurulumun `_internal/rebuild` klasöründe bulunur. Ticari Qt lisansı satın
alınmadı; ücretsiz açık kaynak seçeneği kullanıldı. Bu kaynak erişiminin
uygulama için nasıl kullanılacağı `store/REBUILD.txt` içinde açıklanır.

## 5. Gerçek Windows kontrolünü tamamla

Linux'ta yapılan testler Windows kurulumu, ses sürücüsü ve Store onayının
yerine geçmez. Önce `release/.../OdakPomodoro/OdakPomodoro.exe` dosyasını
çalıştır. EXE ve `_internal` klasörünü birlikte tut. Ardından Windows'un
geliştirici modunu kendi geliştirme bilgisayarında açarak PowerShell'de
oluşan manifesti kaydet:

```powershell
Add-AppxPackage -Register "C:\tam-yol\release\2.2.0.0-store\OdakPomodoro\AppxManifest.xml"
```

Bu, kaynak klasörüne bağlı geliştirme kaydıdır; klasörü taşımadan Başlat
menüsünden uygulamayı test et. Store'dan kurulmuş gerçek paket için ayrıca
Partner Center'ın özel hedef kitle/flight seçeneklerini kullanabilirsin.
MSIX'i dışarıdan kurarak test edeceksen ayrı test imzası gerekir; bu
proje hiçbir test sertifikasını güvenilen köklere otomatik olarak eklemez.

Kontrol listesi:

- Ayrı bir Windows kullanıcı hesabında ilk açılış boş: görev, ana başlık,
  geçmiş veya aktif oturum yok. İlk ana başlık ve görevi ekleyebilirsin.
- 1 dakikalık oturum ve mola sonunda zil çalıyor; otomatik mola çalışıyor.
- Erken Bitir bir Pomodoro sayıyor; Sıfırla kaydetmeden yeniden başlıyor.
- Devam ettir mor sayaçla aynı kaydı uzatıyor; ikinci kez saymıyor.
- Ana pencere/widget senkron; widget kapanınca gizli ana pencere geri geliyor.
- Kapat/aç yarım oturumu duraklatılmış getiriyor; mevcut kayıtlar korunuyor.
- Açık/koyu tema, klavye Tab/Enter, yüksek DPI ve farklı ekran boyutları.
  Arayüz en az 1060×700 mantıksal piksel çalışma alanı için tasarlandı.
- CSV ve SQLite yedek, yazma izni olmayan konumda hata bildirimi.
- Windows Ayarları'ndan kaldırma ve sonraki sürümle veri korunarak güncelleme.
- Windows App Certification Kit ile MSIX'i denetle. Rapordaki başarısız
  kontrolleri düzeltmeden sertifikasyona gönderme. Son raporu sürümle sakla.

`store/previews` Linux'tan alınan arayüz önizlemeleridir. Mağaza için
Windows derlemesinin `screenshots` klasörünü kullan. Bu görseller yalnızca
geçici örnek kayıtlarla oluşturulur; gerçek veritabanını okumaz. Görselleri
gözden geçir; her biri en az 1366×768 PNG olmalı. Pakete örnek kayıt eklenmez.

## 6. Partner Center başvurusunu doldur

1. Ürününde **Start your submission / New submission** aç.
2. **Pricing and availability**: ücretsiz/ücretli kararını ve ülkeleri seç.
   Kod bu kararı otomatik vermez; deneme veya uygulama içi satın alma yoktur.
3. **Properties**: uygun üretkenlik kategorisi; PC; Türkçe. Xbox, mobil
   veya Windows'un Win+W widget paneli desteği iddia etme.
4. **Age ratings**: IARC anketini gerçek özelliklere göre doldur. Bu yerel
   görev takip uygulamasında sohbet, kullanıcılar arası paylaşım, reklam,
   kumar veya uygulama içi satın alma yok. Yaş puanını anket belirler.
5. **Packages**: üretilen `.msix` dosyasını yükle. Kimlik uyumsuzluğu varsa
   manifest alanlarını tahmin etme; Product identity'den tekrar kopyala.
6. **Store listings → Turkish (tr-TR)**: `store/STORE_METINLERI.txt`
   içindeki açıklamaları, Windows ekran görüntülerini ve
   `store/Assets/ListingIcon.png` dosyasını kullan.
7. **Support info**: genel destek adresini ve gizlilik URL'sini gir.
8. **Submission options / Notes for certification**: aynı metin dosyasındaki
   test adımlarını ve `runFullTrust` gerekçesini ekle. Başka hassas yetki yok.
9. Önizlemede ad, yayıncı, fiyat, ülkeler, açıklama ve görüntüleri kontrol et.
   **Submit to the Store** ile Microsoft incelemesine gönder. Yayın tarihi
   ve sertifikasyon sonucu Microsoft tarafından belirlenir; onay garanti değil.

Sonraki sürümde JSON'da örneğin `2.2.1.0` kullan; kimlik/yayıncı aynı kalsın.
İlk üç sürüm parçasından uygun olanı artır, dördüncü parçayı `0` bırak.
Store güncellemeyi kendisi dağıtır; uygulamada ayrı güncelleyici yoktur.

## Resmî kaynaklar — kontrol tarihi 23 Eylül 2026

- Hesap: https://learn.microsoft.com/windows/apps/publish/partner-center/open-a-developer-account
- Bireysel ücretsiz kayıt: https://learn.microsoft.com/windows/apps/publish/whats-new-individual-developer
- Paket/kimlik/imza: https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/app-package-requirements
- MSIX hazırlama: https://learn.microsoft.com/windows/msix/desktop/desktop-to-uwp-manual-conversion
- Paket yükleme: https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/upload-app-packages
- Görseller: https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/screenshots-and-images
- İlkeler: https://learn.microsoft.com/windows/apps/publish/store-policies
- Qt LGPL yükümlülükleri: https://www.qt.io/development/open-source-lgpl-obligations

İlkeler sayfasında yayımlanan yeni sürümün yürürlük tarihi başvuru tarihinden
sonra olabilir. Gönderim gününde geçerli sürümü ve Partner Center'ın gösterdiği
koşulları kontrol et. Hazırlanan paket tüm mağaza koşullarına uygunluk veya
sertifikasyon başarısı garantisi değildir; Windows doğrulaması hâlâ gereklidir.
