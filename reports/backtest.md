# Backtest Report (§8.4)

Projected 2025-26 from 2023-24/2024-25 only, evaluated against what actually happened. 405 players in the backtest population, 150 in the §4.1 draftable pool (computed from actual 2025-26 outcomes, fixed across both scenarios). FG%/FT% are scored as §4.2 volume-weighted impact (FG_IMPACT/FT_IMPACT), not the raw percentage -- that's what valuation actually consumes, and it's what makes them minutes-sensitive like the counting stats.

## Scenario A: actual (known) 2025-26 minutes/GP

### Full population

```
             n     mae    corr
category                      
PTS        405  1.4257  0.9582
REB        405  0.4918  0.9629
AST        405  0.4363  0.9411
STL        405  0.1694  0.8497
BLK        405  0.1374  0.8912
3PM        405  0.2527  0.9218
TOV        405  0.2540  0.9137
FG_IMPACT  405  0.2586  0.7507
FT_IMPACT  405  0.1023  0.7948
```

### Restricted to the §4.1 draftable pool

```
             n     mae    corr
category                      
PTS        150  2.0163  0.9052
REB        150  0.6137  0.9409
AST        150  0.6311  0.9079
STL        150  0.2003  0.7296
BLK        150  0.1780  0.8880
3PM        150  0.3282  0.8977
TOV        150  0.3299  0.8497
FG_IMPACT  150  0.2928  0.8188
FT_IMPACT  150  0.1364  0.8698
```

## Scenario B: previous-season minutes/GP as a naive proxy

### Full population

```
             n     mae    corr
category                      
PTS        405  2.7135  0.8608
REB        405  0.9774  0.8566
AST        405  0.7074  0.8499
STL        405  0.2338  0.7006
BLK        405  0.1698  0.8356
3PM        405  0.3594  0.8354
TOV        405  0.3701  0.8245
FG_IMPACT  405  0.2636  0.7426
FT_IMPACT  405  0.1049  0.7841
```

### Restricted to the §4.1 draftable pool

```
             n     mae    corr
category                      
PTS        150  2.9770  0.8398
REB        150  0.8808  0.8741
AST        150  0.8431  0.8377
STL        150  0.2371  0.6284
BLK        150  0.2053  0.8382
3PM        150  0.4019  0.8362
TOV        150  0.4190  0.7840
FG_IMPACT  150  0.2885  0.8248
FT_IMPACT  150  0.1346  0.8690
```

## Twenty largest misses in each direction, per category (full population)

### PTS

```
           error       direction
player_id                       
johnsca02   4.68   overprojected
steveis01   4.15   overprojected
smartma01   3.34   overprojected
banchpa01   3.29   overprojected
plowdda01   3.27   overprojected
divindo01   3.26   overprojected
smithty02   3.22   overprojected
vassede01   3.16   overprojected
peterdr01   3.13   overprojected
portecr01   3.08   overprojected
wisemja01   3.05   overprojected
foxde01     2.97   overprojected
slawsja01   2.84   overprojected
balllo01    2.84   overprojected
bouchch01   2.82   overprojected
tomlina01   2.72   overprojected
willizi01   2.65   overprojected
quickim01   2.63   overprojected
martico01   2.53   overprojected
turnemy01   2.49   overprojected
alexani01  -8.14  underprojected
brookdi01  -7.57  underprojected
leonaka01  -7.30  underprojected
portemi01  -7.17  underprojected
newtotr01  -6.63  underprojected
brownja02  -6.60  underprojected
avdijde01  -6.14  underprojected
durenja01  -6.01  underprojected
nembhan01  -5.55  underprojected
georgke01  -5.46  underprojected
jeromty01  -5.45  underprojected
holidjr01  -5.40  underprojected
allengr01  -4.63  underprojected
pottemi01  -4.59  underprojected
reaveau01  -4.58  underprojected
georgky01  -4.57  underprojected
johnsja05  -4.49  underprojected
beysa01    -4.37  underprojected
watsope01  -4.11  underprojected
curryst01  -4.08  underprojected
```

### REB

```
           error       direction
player_id                       
wisemja01   2.59   overprojected
collijo01   2.02   overprojected
okongon01   1.98   overprojected
thompam01   1.93   overprojected
embiijo01   1.93   overprojected
willizi02   1.81   overprojected
smithja05   1.67   overprojected
sengual01   1.60   overprojected
gueyemo01   1.56   overprojected
claxtni01   1.50   overprojected
banede01    1.44   overprojected
bealbr01    1.40   overprojected
aytonde01   1.26   overprojected
hachiru01   1.25   overprojected
camarto01   1.20   overprojected
cissosi01   1.17   overprojected
cartewe01   1.14   overprojected
avdijde01   1.14   overprojected
nancepe01   1.11   overprojected
kesslwa01   1.11   overprojected
willial06  -2.96  underprojected
jonesco02  -2.80  underprojected
tatumja01  -2.55  underprojected
robinmi01  -2.07  underprojected
townska01  -2.00  underprojected
strusma01  -1.53  underprojected
williro04  -1.35  underprojected
champju02  -1.31  underprojected
newtotr01  -1.31  underprojected
brownja02  -1.29  underprojected
smithto05  -1.28  underprojected
roddyda01  -1.23  underprojected
edeyza01   -1.23  underprojected
furphjo01  -1.09  underprojected
wembavi01  -1.08  underprojected
martico01  -1.06  underprojected
castlst01  -1.01  underprojected
quetane01  -0.96  underprojected
balllo01   -0.95  underprojected
jokicni01  -0.94  underprojected
```

### AST

```
           error       direction
player_id                       
willizi01   1.96   overprojected
ingrabr01   1.94   overprojected
sabondo01   1.75   overprojected
hendesc01   1.44   overprojected
newtotr01   1.38   overprojected
lavinza01   1.37   overprojected
smartma01   1.31   overprojected
edwaran01   1.30   overprojected
clarkjo01   1.29   overprojected
banede01    1.29   overprojected
blackle01   1.17   overprojected
barrerj01   1.11   overprojected
embiijo01   1.06   overprojected
willima07   1.05   overprojected
monkma01    1.04   overprojected
adebaba01   1.01   overprojected
strusma01   1.01   overprojected
herroty01   0.98   overprojected
martico01   0.96   overprojected
bealbr01    0.88   overprojected
johnsja05  -3.40  underprojected
castlst01  -2.50  underprojected
spencca01  -2.44  underprojected
avdijde01  -2.32  underprojected
nembhan01  -2.28  underprojected
suggsja01  -2.08  underprojected
holidjr01  -2.04  underprojected
jeromty01  -1.85  underprojected
giddejo01  -1.79  underprojected
porteke02  -1.65  underprojected
jokicni01  -1.52  underprojected
georgky01  -1.51  underprojected
mitchda01  -1.50  underprojected
claxtni01  -1.45  underprojected
gueyemo01  -1.44  underprojected
daniedy01  -1.39  underprojected
jaqueja01  -1.36  underprojected
moranja01  -1.35  underprojected
cunnica01  -1.35  underprojected
kesslwa01  -1.34  underprojected
```

### STL

```
           error       direction
player_id                       
daniedy01   0.74   overprojected
jaqueja01   0.54   overprojected
larsspe01   0.43   overprojected
embiijo01   0.39   overprojected
poolejo01   0.39   overprojected
nesmiaa01   0.39   overprojected
murraja01   0.38   overprojected
strusma01   0.36   overprojected
gilgesh01   0.35   overprojected
nembhan01   0.35   overprojected
camarto01   0.34   overprojected
easonta01   0.33   overprojected
vassede01   0.33   overprojected
braunch01   0.33   overprojected
willije02   0.33   overprojected
walkeja02   0.32   overprojected
chrisma02   0.32   overprojected
jonesco02   0.31   overprojected
colliza01   0.30   overprojected
whiteda01   0.29   overprojected
steveis01  -1.04  underprojected
thybuma01  -0.80  underprojected
slawsja01  -0.79  underprojected
kesslwa01  -0.67  underprojected
pippesc02  -0.64  underprojected
clarkbr01  -0.62  underprojected
newtotr01  -0.57  underprojected
sharpsh01  -0.54  underprojected
leonaka01  -0.52  underprojected
payneca01  -0.51  underprojected
smithdr01  -0.51  underprojected
allengr01  -0.50  underprojected
thompau01  -0.50  underprojected
bridgmi01  -0.49  underprojected
greenja02  -0.47  underprojected
willizi02  -0.47  underprojected
randlju01  -0.46  underprojected
porteke02  -0.46  underprojected
goodwjo01  -0.45  underprojected
portemi01  -0.45  underprojected
```

### BLK

```
           error       direction
player_id                       
kesslwa01   0.91   overprojected
gueyemo01   0.70   overprojected
thompam01   0.67   overprojected
claxtni01   0.50   overprojected
gaffoda01   0.49   overprojected
johnsja05   0.47   overprojected
sharpda01   0.47   overprojected
watsope01   0.45   overprojected
whiteda01   0.43   overprojected
simsje01    0.42   overprojected
clingdo01   0.41   overprojected
jeffrda01   0.40   overprojected
easonta01   0.39   overprojected
nurkiju01   0.39   overprojected
holidjr01   0.37   overprojected
poeltja01   0.37   overprojected
smithty02   0.36   overprojected
toppiob01   0.35   overprojected
holmgch01   0.34   overprojected
murphtr02   0.32   overprojected
murrake02  -0.69  underprojected
slawsja01  -0.61  underprojected
freemen01  -0.56  underprojected
huffja01   -0.53  underprojected
bouchch01  -0.53  underprojected
missiyv01  -0.51  underprojected
livelde01  -0.50  underprojected
sarral01   -0.48  underprojected
horfoal01  -0.46  underprojected
jarrede01  -0.44  underprojected
edeyza01   -0.43  underprojected
jacksgg01  -0.40  underprojected
stewais01  -0.40  underprojected
jonesde02  -0.40  underprojected
willial06  -0.39  underprojected
maxeyty01  -0.34  underprojected
wiggian01  -0.34  underprojected
leverca01  -0.33  underprojected
barnesc01  -0.33  underprojected
bridgmi01  -0.32  underprojected
```

### 3PM

```
           error       direction
player_id                       
steveis01   0.92   overprojected
murrake02   0.89   overprojected
daniedy01   0.85   overprojected
willija06   0.80   overprojected
peterdr01   0.75   overprojected
whitmca01   0.73   overprojected
grimequ01   0.72   overprojected
banede01    0.65   overprojected
willial06   0.64   overprojected
jamesle01   0.62   overprojected
banchpa01   0.62   overprojected
jarrede01   0.62   overprojected
johnsca02   0.60   overprojected
moranja01   0.59   overprojected
markkla01   0.58   overprojected
sarral01    0.58   overprojected
willibr03   0.57   overprojected
balllo01    0.57   overprojected
herroty01   0.56   overprojected
jacksgg01   0.56   overprojected
okongon01  -1.29  underprojected
newtotr01  -1.25  underprojected
kesslwa01  -1.05  underprojected
jeromty01  -1.02  underprojected
camarto01  -1.02  underprojected
adebaba01  -1.01  underprojected
portemi01  -0.88  underprojected
westbru01  -0.87  underprojected
holidjr01  -0.85  underprojected
alexani01  -0.85  underprojected
nembhan01  -0.85  underprojected
sheppre01  -0.83  underprojected
portibo01  -0.83  underprojected
princta02  -0.82  underprojected
murraja01  -0.82  underprojected
strusma01  -0.80  underprojected
gordoaa01  -0.76  underprojected
clingdo01  -0.74  underprojected
chrisma02  -0.73  underprojected
leonaka01  -0.72  underprojected
```

### TOV

```
           error       direction
player_id                       
smartma01   0.87   overprojected
jeffrda01   0.81   overprojected
wembavi01   0.73   overprojected
willizi01   0.68   overprojected
newtotr01   0.68   overprojected
robindu01   0.67   overprojected
plowdda01   0.63   overprojected
johnsca02   0.60   overprojected
barrerj01   0.60   overprojected
bridgmi01   0.60   overprojected
mcgowbr01   0.59   overprojected
jonessp01   0.56   overprojected
vassede01   0.56   overprojected
bouyeja01   0.54   overprojected
peterdr01   0.54   overprojected
walteja01   0.52   overprojected
clarkjo01   0.52   overprojected
hylanbo01   0.52   overprojected
adebaba01   0.48   overprojected
mykhasv01   0.48   overprojected
kesslwa01  -1.63  underprojected
holidjr01  -1.32  underprojected
brownja02  -1.29  underprojected
jarrede01  -1.15  underprojected
avdijde01  -1.15  underprojected
portemi01  -1.11  underprojected
murrade01  -1.05  underprojected
johnsja05  -1.05  underprojected
georgky01  -0.96  underprojected
sharpsh01  -0.92  underprojected
pippesc02  -0.87  underprojected
jokicni01  -0.79  underprojected
castlst01  -0.74  underprojected
meltode01  -0.73  underprojected
edeyza01   -0.72  underprojected
reaveau01  -0.69  underprojected
brookdi01  -0.68  underprojected
anthoco01  -0.68  underprojected
antetgi01  -0.67  underprojected
siakapa01  -0.67  underprojected
```

### FG_IMPACT

```
           error       direction
player_id                       
adebaba01   0.98   overprojected
okongon01   0.95   overprojected
allengr01   0.95   overprojected
bealbr01    0.94   overprojected
tatumja01   0.93   overprojected
clarkbr01   0.92   overprojected
whiteda01   0.90   overprojected
whitede01   0.89   overprojected
nesmiaa01   0.88   overprojected
peterdr01   0.87   overprojected
joneshe01   0.79   overprojected
wagnemo01   0.74   overprojected
hayeski01   0.73   overprojected
moranja01   0.71   overprojected
poolejo01   0.63   overprojected
turnemy01   0.63   overprojected
jovicni01   0.62   overprojected
easonta01   0.60   overprojected
fultzma01   0.57   overprojected
lopezbr01   0.55   overprojected
willial06  -1.18  underprojected
jeffrda01  -0.98  underprojected
antetgi01  -0.88  underprojected
gilgesh01  -0.80  underprojected
georgke01  -0.78  underprojected
prospol01  -0.77  underprojected
aytonde01  -0.73  underprojected
edwaran01  -0.72  underprojected
barnesc01  -0.71  underprojected
willico04  -0.69  underprojected
pullizy01  -0.66  underprojected
gueyemo01  -0.65  underprojected
murrade01  -0.64  underprojected
jacksgg01  -0.63  underprojected
gillan01   -0.62  underprojected
colliis01  -0.62  underprojected
edeyza01   -0.61  underprojected
willizi01  -0.60  underprojected
mitchdo01  -0.58  underprojected
colliza01  -0.58  underprojected
```

### FT_IMPACT

```
           error       direction
player_id                       
mobleev01   0.60   overprojected
goberru01   0.57   overprojected
clarkbr01   0.52   overprojected
sarrol01    0.41   overprojected
newtotr01   0.40   overprojected
siakapa01   0.38   overprojected
martico01   0.37   overprojected
antetgi01   0.34   overprojected
furphjo01   0.33   overprojected
tshieos01   0.32   overprojected
robinmi01   0.31   overprojected
ighodos01   0.28   overprojected
weslebl01   0.26   overprojected
nurkiju01   0.26   overprojected
thompau01   0.25   overprojected
russeda01   0.24   overprojected
smithto05   0.24   overprojected
eubandr01   0.23   overprojected
edwaran01   0.23   overprojected
jovicni01   0.22   overprojected
georgke01  -0.54  underprojected
moranja01  -0.47  underprojected
leonaka01  -0.47  underprojected
alexani01  -0.43  underprojected
porteke02  -0.39  underprojected
roddyda01  -0.35  underprojected
jeffrda01  -0.34  underprojected
markkla01  -0.32  underprojected
banchpa01  -0.30  underprojected
thompam01  -0.30  underprojected
reaveau01  -0.29  underprojected
livelde01  -0.28  underprojected
portemi01  -0.28  underprojected
butleji01  -0.26  underprojected
jokicni01  -0.26  underprojected
duranke01  -0.25  underprojected
toppiob01  -0.25  underprojected
millebr02  -0.25  underprojected
steveis01  -0.24  underprojected
hayeski01  -0.24  underprojected
```
