# Local OCR comparison: 2026-09-08

Environment: Windows AMD64, CPython 3.13.1, PaddleOCR 3.7.0, PaddlePaddle CPU 3.3.1, PaddleX 3.7.2. PP-OCRv5_server_det + latin_PP-OCRv5_mobile_rec (lang=vi), MKL-DNN disabled. Tesseract 5.5.2 via tesserocr 2.10.0, vie+eng, PSM 3.

No fallback was used. Both images reused the same Paddle process. Original image SHA-256 values were unchanged. Tesseract timings include result-cache hits, so these timings are not a speed benchmark. Paddle includes initialization on the first image. Word-box counts/confidences (Tesseract) and detected-span counts/confidences (Paddle) are not directly comparable.

| Image | Engine | Blocks | Mean confidence | Seconds |
| --- | --- | ---: | ---: | ---: |
| cmt4.png | tesseract | 25 | 0.841 | 0.01 |
| cmt4.png | paddle | 9 | 0.910 | 38.33 |
| cmt5.png | tesseract | 24 | 0.902 | 0.01 |
| cmt5.png | paddle | 7 | 0.956 | 31.65 |

Observed result: Tesseract preserved Vietnamese accents more accurately on these two screenshots. Paddle detected the header date on cmt5 but omitted many accented letters in the caption. On cmt4 its extracted body retains a joined carousel counter and two drawing symbols. High confidence did not imply correct Vietnamese text. Both providers remain selectable; this experiment does not establish Paddle as the better default for production.

## cmt4.png

### tesseract

Raw OCR:

```text
mer.hii > pet threads 01/03/2026

© cho tui hình xấu nhất của pet bạn i
tui vẽ meme cho 1/2

© 201K Qa47K %33K 62k
```

ThreadsExtractor body_text:

```text
cho tui hình xấu nhất của pet bạn i
tui vẽ meme cho
```

### paddle

Raw OCR:

```text
mer.hii > pet threads 01/03/2026
cho tui hình xu nht ca pet bn i
tui vē meme cho1/2
*
*
20,1K Q 4,7K 3,3K 2K
```

ThreadsExtractor body_text:

```text
cho tui hình xu nht ca pet bn i
tui vē meme cho1/2
*
*
```

## cmt5.png

### tesseract

Raw OCR:

```text
lộn syh.27.7
4+) Minh mở sap buôn nồi a

Ham nhớ meme ai vẽ nhưng xin phép mượn buôn ít nồi nha ®

a
```

ThreadsExtractor body_text:

```text
Minh mở sap buôn nồi a
Ham nhớ meme ai vẽ nhưng xin phép mượn buôn ít nồi nha ®
```

### paddle

Raw OCR:

```text
syh.27.7 07/07/2026
Mình m sp buôn ni
Hăm nh meme ai v nhưng xin phép mưn buôn ít ni nha
189 Q 17 G 17 3
```

ThreadsExtractor body_text:

```text
Mình m sp buôn ni
Hăm nh meme ai v nhưng xin phép mưn buôn ít ni nha
```
