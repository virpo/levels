#!/usr/bin/env bash
# Card art per tier: the same clay caveman as the lineup (art/refs/tier-N.png is his crop), now in his era's world,
# softly out of focus so he stays the subject. Only missing images are generated.
set -uo pipefail
cd "$(dirname "$0")"
BASE="Use the attached clay caveman figure as the exact same character in the exact same pose, outfit and props: the same face, beard, hair and proportions, the same handmade plasticine claymation look. Make a landscape card illustration: the character waist-up, centred, filling about two thirds of the height, facing the viewer, friendly. Behind him:"
TAIL="The background is softly out of focus with gentle bokeh and shallow depth of field, slightly muted so he stands out, like a miniature film set photographed with a macro lens. No text, no letters, no frame, no border."
gen() { [ -f "../art/raw/tier-$1.png" ] && { echo "skip $1"; return; }; ./gen.sh "tier-$1" "$BASE $2 $TAIL" "../art/refs/tier-$1.png"; }
gen 1 "a prehistoric valley with giant ferns, morning mist and a distant smoking volcano."
gen 2 "the inside of a cave lit by a campfire, warm ember light and cave paintings on the walls."
gen 3 "an early village with wooden carts and stone wheels at golden hour."
gen 4 "a bronze-age workshop with copper pots and a warm glowing kiln."
gen 5 "a blacksmith's forge with an anvil and flying sparks."
gen 6 "a steam-age workshop with brass pipes, gauges and soft steam."
gen 7 "a 1920s electrical laboratory with glowing light bulbs and coiled wires."
gen 8 "a calm modern desk with monitors and the soft glow of circuit boards."
gen 9 "the window of a space station with the Earth and stars outside."
gen 10 "a calm zen garden at dusk with raked sand, smooth stones and a soft paper lantern."
