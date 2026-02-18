# Numpad notation (input display)

We use **numpad notation** for directions. Each row in the cascade is: **direction/input** + **frame count**.

## Direction layout (numpad 1–9)

```
7 8 9     Up-Back   Up   Up-Forward
4 5 6  =  Back   Neutral  Forward
1 2 3     Down-Back Down Down-Forward
```

- **5** or **N** = neutral (no direction)
- **6** = forward
- **4** = back
- **3** = down-forward
- **2** = down
- **8** = up
- **1** = down-back, **7** = up-back, **9** = up-forward

## Attacks (after direction, optional)

- **P** = punch, **K** = kick  
- **L** = light (blue), **M** = medium (yellow), **H** = heavy (red)  
- Examples: **6P** = forward punch, **4HP** = back heavy punch, **2K** = down kick, **N** or **5** = neutral

## Row format

Each line in the cascade: `[direction][attack] [frames]`  
Examples: `3 19`, `6 4`, `6 5`, `N 1`, `4 14`, `4HP 4`
