# Backtest Report (§8.4)

Projected 2025-26 from 2023-24/2024-25 only, evaluated against what actually happened. 405 players in the backtest population, 150 in the §4.1 draftable pool (computed from actual 2025-26 outcomes, fixed across both scenarios). FG%/FT% are scored as §4.2 volume-weighted impact (FG_IMPACT/FT_IMPACT), not the raw percentage -- that's what valuation actually consumes, and it's what makes them minutes-sensitive like the counting stats.

## Scenario A: actual (known) 2025-26 minutes/GP

### Full population

```
             n     mae    corr
category                      
PTS        405  1.5234  0.9534
REB        405  0.4994  0.9598
AST        405  0.4581  0.9374
STL        405  0.1849  0.8335
BLK        405  0.1374  0.8821
3PM        405  0.2578  0.9189
TOV        405  0.2587  0.9095
FG_IMPACT  405  0.2822  0.6900
FT_IMPACT  405  0.1142  0.7323
```

### Restricted to the §4.1 draftable pool

```
             n     mae    corr
category                      
PTS        150  2.2725  0.8924
REB        150  0.6497  0.9339
AST        150  0.6933  0.8997
STL        150  0.2271  0.6862
BLK        150  0.1749  0.8796
3PM        150  0.3405  0.8927
TOV        150  0.3501  0.8400
FG_IMPACT  150  0.3606  0.7414
FT_IMPACT  150  0.1612  0.8131
```

## Scenario B: previous-season minutes/GP as a naive proxy

### Full population

```
             n     mae    corr
category                      
PTS        405  2.7523  0.8581
REB        405  0.9618  0.8538
AST        405  0.7163  0.8473
STL        405  0.2426  0.6932
BLK        405  0.1677  0.8292
3PM        405  0.3608  0.8351
TOV        405  0.3734  0.8207
FG_IMPACT  405  0.2919  0.6791
FT_IMPACT  405  0.1157  0.7224
```

### Restricted to the §4.1 draftable pool

```
             n     mae    corr
category                      
PTS        150  3.1635  0.8315
REB        150  0.8992  0.8662
AST        150  0.8886  0.8288
STL        150  0.2680  0.5947
BLK        150  0.2052  0.8284
3PM        150  0.4119  0.8339
TOV        150  0.4421  0.7732
FG_IMPACT  150  0.3564  0.7377
FT_IMPACT  150  0.1584  0.8100
```

## regression_k grid search (§3.3 tuning)

```
          default_k  default_mae  tuned_k  tuned_mae  improvement_pct
category                                                             
PTS             100       1.5234      100     1.5234              0.0
REB             200       0.4994      200     0.4994              0.0
AST             100       0.4581      100     0.4581              0.0
STL             500       0.1849      500     0.1849              0.0
BLK             400       0.1374      400     0.1374              0.0
3PM             100       0.2578      100     0.2578              0.0
TOV             500       0.2587      500     0.2587              0.0
FG              800       0.2824     1000     0.2822              0.1
FT             1200       0.1152      800     0.1142              0.9
```

## Twenty largest misses in each direction, per category (full population)

### PTS

```
           error       direction
player_id                       
johnsca02   4.68   overprojected
steveis01   4.02   overprojected
plowdda01   3.27   overprojected
divindo01   3.26   overprojected
smartma01   3.14   overprojected
peterdr01   3.11   overprojected
foxde01     2.97   overprojected
portecr01   2.95   overprojected
wisemja01   2.88   overprojected
vassede01   2.87   overprojected
balllo01    2.84   overprojected
slawsja01   2.77   overprojected
bouchch01   2.60   overprojected
tomlina01   2.58   overprojected
martico01   2.52   overprojected
quickim01   2.50   overprojected
turnemy01   2.49   overprojected
smithty02   2.48   overprojected
saricda01   2.39   overprojected
huffja01    2.30   overprojected
leonaka01  -8.49  underprojected
alexani01  -8.14  underprojected
brookdi01  -7.62  underprojected
portemi01  -7.17  underprojected
curryst01  -7.06  underprojected
durenja01  -6.95  underprojected
newtotr01  -6.77  underprojected
georgke01  -6.73  underprojected
brownja02  -6.60  underprojected
avdijde01  -6.44  underprojected
holidjr01  -6.31  underprojected
nembhan01  -5.63  underprojected
jeromty01  -5.45  underprojected
georgky01  -5.28  underprojected
johnsja05  -4.98  underprojected
duranke01  -4.89  underprojected
allengr01  -4.68  underprojected
wembavi01  -4.67  underprojected
jamesle01  -4.62  underprojected
watsope01  -4.60  underprojected
```

### REB

```
           error       direction
player_id                       
wisemja01   2.47   overprojected
collijo01   2.02   overprojected
okongon01   1.82   overprojected
embiijo01   1.77   overprojected
willizi02   1.70   overprojected
gueyemo01   1.56   overprojected
thompam01   1.48   overprojected
banede01    1.44   overprojected
claxtni01   1.44   overprojected
bealbr01    1.34   overprojected
aytonde01   1.26   overprojected
hachiru01   1.25   overprojected
sengual01   1.11   overprojected
camarto01   1.10   overprojected
cartewe01   1.08   overprojected
lavinza01   1.08   overprojected
smithja05   1.08   overprojected
steveis01   1.06   overprojected
nancepe01   1.05   overprojected
mamuksa01   1.04   overprojected
willial06  -2.98  underprojected
jonesco02  -2.85  underprojected
tatumja01  -2.55  underprojected
robinmi01  -2.07  underprojected
townska01  -2.04  underprojected
wembavi01  -1.81  underprojected
edeyza01   -1.69  underprojected
wareke01   -1.60  underprojected
strusma01  -1.53  underprojected
clingdo01  -1.44  underprojected
champju02  -1.43  underprojected
castlst01  -1.41  underprojected
furphjo01  -1.39  underprojected
newtotr01  -1.36  underprojected
williro04  -1.35  underprojected
smithto05  -1.32  underprojected
roddyda01  -1.31  underprojected
brownja02  -1.29  underprojected
leonaka01  -1.23  underprojected
daniedy01  -1.23  underprojected
```

### AST

```
           error       direction
player_id                       
ingrabr01   1.94   overprojected
willizi01   1.82   overprojected
sabondo01   1.75   overprojected
lavinza01   1.37   overprojected
newtotr01   1.32   overprojected
banede01    1.29   overprojected
smartma01   1.28   overprojected
clarkjo01   1.23   overprojected
blackle01   1.14   overprojected
edwaran01   1.07   overprojected
monkma01    1.04   overprojected
embiijo01   1.02   overprojected
adebaba01   1.01   overprojected
strusma01   1.01   overprojected
barrerj01   0.98   overprojected
willima07   0.96   overprojected
martico01   0.96   overprojected
herroty01   0.92   overprojected
bealbr01    0.84   overprojected
jeffrda01   0.80   overprojected
johnsja05  -3.60  underprojected
castlst01  -3.18  underprojected
spencca01  -2.53  underprojected
avdijde01  -2.44  underprojected
nembhan01  -2.35  underprojected
giddejo01  -2.33  underprojected
suggsja01  -2.23  underprojected
holidjr01  -2.18  underprojected
daniedy01  -1.87  underprojected
jeromty01  -1.85  underprojected
georgky01  -1.82  underprojected
porteke02  -1.81  underprojected
cunnica01  -1.73  underprojected
jokicni01  -1.54  underprojected
jaqueja01  -1.51  underprojected
mitchda01  -1.50  underprojected
rolliry01  -1.49  underprojected
claxtni01  -1.47  underprojected
gueyemo01  -1.44  underprojected
moranja01  -1.43  underprojected
```

### STL

```
           error       direction
player_id                       
daniedy01   0.51   overprojected
jaqueja01   0.49   overprojected
larsspe01   0.39   overprojected
murraja01   0.38   overprojected
poolejo01   0.38   overprojected
nesmiaa01   0.38   overprojected
strusma01   0.36   overprojected
embiijo01   0.35   overprojected
gilgesh01   0.35   overprojected
nembhan01   0.33   overprojected
willije02   0.32   overprojected
vassede01   0.31   overprojected
colliza01   0.30   overprojected
camarto01   0.30   overprojected
braunch01   0.30   overprojected
jonesco02   0.29   overprojected
easonta01   0.28   overprojected
trentga02   0.27   overprojected
hylanbo01   0.26   overprojected
jacksqu01   0.25   overprojected
steveis01  -1.06  underprojected
thybuma01  -0.80  underprojected
slawsja01  -0.80  underprojected
leonaka01  -0.74  underprojected
kesslwa01  -0.70  underprojected
pippesc02  -0.67  underprojected
jamesle01  -0.65  underprojected
butleji01  -0.64  underprojected
clarkbr01  -0.62  underprojected
sharpsh01  -0.61  underprojected
georgpa01  -0.61  underprojected
thompau01  -0.59  underprojected
newtotr01  -0.58  underprojected
curryst01  -0.57  underprojected
payneca01  -0.54  underprojected
wallaca01  -0.53  underprojected
greenja02  -0.53  underprojected
hollaro01  -0.52  underprojected
allengr01  -0.51  underprojected
smithdr01  -0.51  underprojected
```

### BLK

```
           error       direction
player_id                       
kesslwa01   0.81   overprojected
gueyemo01   0.70   overprojected
thompam01   0.59   overprojected
gaffoda01   0.49   overprojected
claxtni01   0.48   overprojected
johnsja05   0.44   overprojected
sharpda01   0.43   overprojected
simsje01    0.42   overprojected
jeffrda01   0.40   overprojected
whiteda01   0.38   overprojected
easonta01   0.36   overprojected
watsope01   0.36   overprojected
poeltja01   0.36   overprojected
nurkiju01   0.35   overprojected
toppiob01   0.35   overprojected
smithty02   0.32   overprojected
murphtr02   0.31   overprojected
yurtsom01   0.30   overprojected
tatumja01   0.30   overprojected
wisemja01   0.29   overprojected
horfoal01  -0.75  underprojected
murrake02  -0.71  underprojected
sarral01   -0.65  underprojected
missiyv01  -0.63  underprojected
livelde01  -0.62  underprojected
slawsja01  -0.62  underprojected
freemen01  -0.57  underprojected
bouchch01  -0.56  underprojected
huffja01   -0.53  underprojected
edeyza01   -0.52  underprojected
jacksgg01  -0.45  underprojected
stewais01  -0.44  underprojected
jarrede01  -0.44  underprojected
jordade01  -0.43  underprojected
jonesde02  -0.40  underprojected
willial06  -0.40  underprojected
coulibi01  -0.38  underprojected
barnesc01  -0.37  underprojected
maxeyty01  -0.35  underprojected
leverca01  -0.35  underprojected
```

### 3PM

```
           error       direction
player_id                       
steveis01   0.91   overprojected
murrake02   0.85   overprojected
daniedy01   0.78   overprojected
willija06   0.76   overprojected
peterdr01   0.74   overprojected
grimequ01   0.68   overprojected
banede01    0.65   overprojected
willial06   0.63   overprojected
jarrede01   0.62   overprojected
johnsca02   0.60   overprojected
whitmca01   0.60   overprojected
markkla01   0.58   overprojected
moranja01   0.58   overprojected
balllo01    0.57   overprojected
willibr03   0.56   overprojected
huffja01    0.54   overprojected
smithdr01   0.54   overprojected
herroty01   0.54   overprojected
banchpa01   0.53   overprojected
divindo01   0.53   overprojected
okongon01  -1.30  underprojected
newtotr01  -1.27  underprojected
kesslwa01  -1.05  underprojected
camarto01  -1.05  underprojected
jeromty01  -1.02  underprojected
westbru01  -1.02  underprojected
sheppre01  -1.02  underprojected
adebaba01  -1.01  underprojected
holidjr01  -1.00  underprojected
curryst01  -0.88  underprojected
portemi01  -0.88  underprojected
nembhan01  -0.85  underprojected
alexani01  -0.85  underprojected
princta02  -0.85  underprojected
chrisma02  -0.84  underprojected
portibo01  -0.84  underprojected
leonaka01  -0.83  underprojected
murraja01  -0.82  underprojected
strusma01  -0.80  underprojected
clingdo01  -0.78  underprojected
```

### TOV

```
           error       direction
player_id                       
smartma01   0.83   overprojected
jeffrda01   0.81   overprojected
newtotr01   0.66   overprojected
robindu01   0.65   overprojected
willizi01   0.63   overprojected
plowdda01   0.63   overprojected
johnsca02   0.60   overprojected
bridgmi01   0.60   overprojected
barrerj01   0.56   overprojected
mcgowbr01   0.54   overprojected
peterdr01   0.54   overprojected
jonessp01   0.53   overprojected
bouyeja01   0.53   overprojected
vassede01   0.53   overprojected
wembavi01   0.51   overprojected
hylanbo01   0.49   overprojected
adebaba01   0.48   overprojected
mykhasv01   0.48   overprojected
bridgmi02   0.46   overprojected
clarkjo01   0.46   overprojected
kesslwa01  -1.68  underprojected
holidjr01  -1.44  underprojected
brownja02  -1.29  underprojected
avdijde01  -1.19  underprojected
jarrede01  -1.15  underprojected
johnsja05  -1.11  underprojected
portemi01  -1.11  underprojected
georgky01  -1.08  underprojected
sharpsh01  -1.06  underprojected
murrade01  -1.05  underprojected
castlst01  -0.97  underprojected
pippesc02  -0.90  underprojected
westbru01  -0.81  underprojected
jokicni01  -0.80  underprojected
edeyza01   -0.80  underprojected
carrica01  -0.78  underprojected
giddejo01  -0.78  underprojected
duranke01  -0.74  underprojected
meltode01  -0.73  underprojected
jamesle01  -0.72  underprojected
```

### FG_IMPACT

```
           error       direction
player_id                       
adebaba01   0.98   overprojected
okongon01   0.94   overprojected
tatumja01   0.93   overprojected
clarkbr01   0.90   overprojected
nesmiaa01   0.88   overprojected
peterdr01   0.87   overprojected
allengr01   0.85   overprojected
joneshe01   0.79   overprojected
bealbr01    0.74   overprojected
wagnemo01   0.74   overprojected
moranja01   0.71   overprojected
hayeski01   0.71   overprojected
whitede01   0.70   overprojected
whiteda01   0.67   overprojected
poolejo01   0.63   overprojected
fultzma01   0.57   overprojected
turnemy01   0.56   overprojected
easonta01   0.55   overprojected
jovicni01   0.55   overprojected
wiggiaa01   0.54   overprojected
jamesle01  -1.88  underprojected
duranke01  -1.54  underprojected
curryst01  -1.35  underprojected
antetgi01  -1.22  underprojected
willial06  -1.18  underprojected
derozde01  -1.14  underprojected
butleji01  -1.05  underprojected
jeffrda01  -0.98  underprojected
georgke01  -0.86  underprojected
leonaka01  -0.83  underprojected
gillan01   -0.82  underprojected
prospol01  -0.81  underprojected
gilgesh01  -0.80  underprojected
edwaran01  -0.79  underprojected
jacksgg01  -0.79  underprojected
durenja01  -0.77  underprojected
barnesc01  -0.77  underprojected
colliis01  -0.76  underprojected
willico04  -0.76  underprojected
edeyza01   -0.74  underprojected
```

### FT_IMPACT

```
           error       direction
player_id                       
mobleev01   0.57   overprojected
clarkbr01   0.51   overprojected
goberru01   0.50   overprojected
sarrol01    0.41   overprojected
newtotr01   0.39   overprojected
martico01   0.36   overprojected
siakapa01   0.33   overprojected
tshieos01   0.32   overprojected
robinmi01   0.31   overprojected
antetgi01   0.26   overprojected
ighodos01   0.26   overprojected
furphjo01   0.24   overprojected
weslebl01   0.24   overprojected
smithto05   0.24   overprojected
russeda01   0.23   overprojected
eubandr01   0.23   overprojected
thompau01   0.22   overprojected
nurkiju01   0.22   overprojected
harteis01   0.21   overprojected
colliza01   0.21   overprojected
georgke01  -0.72  underprojected
butleji01  -0.67  underprojected
duranke01  -0.67  underprojected
leonaka01  -0.60  underprojected
curryst01  -0.57  underprojected
derozde01  -0.50  underprojected
moranja01  -0.47  underprojected
banchpa01  -0.44  underprojected
alexani01  -0.43  underprojected
porteke02  -0.39  underprojected
roddyda01  -0.36  underprojected
wembavi01  -0.36  underprojected
thompam01  -0.36  underprojected
jeffrda01  -0.34  underprojected
jamesle01  -0.34  underprojected
hendesc01  -0.34  underprojected
markkla01  -0.32  underprojected
millebr02  -0.32  underprojected
livelde01  -0.31  underprojected
jokicni01  -0.31  underprojected
```
