// The colour of the surface is the colour of what it is showing.
//
// The skin this surface is modelled on takes its highlight from the artwork of
// whatever has the remote and states it as `fhls*-;0.45;0.9`: the HUE comes
// from the picture, the lightness and the saturation are fixed by the skin. It
// is the right way round — a picture's own colour is as often mud as it is a
// colour, and a ring drawn in mud on a near-black ground cannot be seen from a
// sofa. So the hue is asked of the picture and the rest is ours.

/** enough of a colour to be worth counting: the greys in a poster outnumber the
 *  colour in it, and averaged flat they answer grey every time */
const ENOUGH = 0.18;

let showing = '';
let asked = 0;

function paint(colour: string) {
	if (colour === showing) return;
	showing = colour;
	if (colour) document.documentElement.style.setProperty('--accent', colour);
	else document.documentElement.style.removeProperty('--accent');
}

/** the circular mean of the hues, weighted by how much colour each pixel has.
 *  Averaged as plain numbers, red at 350 and red at 10 answer cyan. */
function hueOf(pixels: Uint8ClampedArray): number | null {
	let x = 0;
	let y = 0;
	let weight = 0;
	for (let i = 0; i < pixels.length; i += 4) {
		if (pixels[i + 3] < 200) continue;
		const r = pixels[i] / 255;
		const g = pixels[i + 1] / 255;
		const b = pixels[i + 2] / 255;
		const max = Math.max(r, g, b);
		const min = Math.min(r, g, b);
		const light = (max + min) / 2;
		if (light < 0.12 || light > 0.92) continue;
		const span = max - min;
		if (span === 0) continue;
		const saturation = span / (1 - Math.abs(2 * light - 1));
		if (saturation < ENOUGH) continue;

		let hue: number;
		if (max === r) hue = ((g - b) / span + 6) % 6;
		else if (max === g) hue = (b - r) / span + 2;
		else hue = (r - g) / span + 4;
		hue *= 60;

		// a strong colour in the middle of the range says more about the picture
		// than a pale one at either end of it
		const says = saturation * (1 - Math.abs(light - 0.5));
		x += Math.cos((hue * Math.PI) / 180) * says;
		y += Math.sin((hue * Math.PI) / 180) * says;
		weight += says;
	}
	if (weight < 0.5) return null;
	const hue = (Math.atan2(y, x) * 180) / Math.PI;
	return (hue + 360) % 360;
}

export const tint = {
	/** take the colour of this picture, once it has arrived */
	from(url: string) {
		const mine = ++asked;
		const image = new Image();
		// the player serves its own artwork, so the canvas stays readable — an
		// address from anywhere else would poison it and this would throw
		image.src = url;
		image
			.decode()
			.then(() => {
				if (mine !== asked) return;
				const canvas = document.createElement('canvas');
				canvas.width = 24;
				canvas.height = 24;
				const paper = canvas.getContext('2d', { willReadFrequently: true });
				if (!paper) return;
				paper.drawImage(image, 0, 0, 24, 24);
				const hue = hueOf(paper.getImageData(0, 0, 24, 24).data);
				paint(hue === null ? '' : `hsl(${hue.toFixed(0)} 62% 55%)`);
			})
			.catch(() => {
				if (mine === asked) paint('');
			});
	},
	/** nothing is being shown, so the surface goes back to being OPUS */
	rest() {
		asked += 1;
		paint('');
	}
};
