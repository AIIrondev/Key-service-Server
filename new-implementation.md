# Merge of Inventarsystem

We'll discuss how we will merge this repo with Inventarsystem -> https://github.com/AIIrondev/Inventarsystem/tree/nuitka and how this will work in the future.

## Content

1. Why merge in the first place?
2. What to merge and what to keep split?
3. Will it be made accesable via the main website?

## Why merge in the first place? 

THis will be simple to anwser, because we need to merge it to get more efficiency out of the server to optimise utilisation for the most users posible.


## What to merge and what to keep split?

For meging espeacialy the database moves into focus, because this is the point of combined intresst and the programm with the most computing need espeacaly in regarts to the RAM ussage. This will be possible by giving each User there own db in the Mongodb Database automaticly when starting a new client version.
The individual Inventory systems will be keept appart, it id beeing bound to individual subaddressesaccording to the schoolname. This will be automatat first the generation and the removal if the administrator is pressind a button in the according admin menu if the user ether quit there Key or the key expiered.

## will it be made accesable via the main website?

Yes but only the administrative view for reviewing the key and the state of the appropriate part and for the individual users it has to be in the subaddress