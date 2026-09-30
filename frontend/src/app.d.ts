declare global {
	namespace App {}
}

export {};

type Heard =
	| { text: string; done: boolean }
	| { unheard: true }
	| { error: number };

declare global {
	interface Window {
		/** the television wrapper, when the page is running inside one */
		/** answered by whatever is on screen: did it take the back press */
		opusBack?: () => boolean;
		/** answered by the page when the remote's media keys reach the wrapper's
		    media session: next, previous, stop */
		opusTvKey?: (command: string) => void;
		/** the remote's microphone key, sent while a keyboard has taken it */
		opusListen?: () => void;
		/** what the box's recognizer has heard so far, or why it heard nothing */
		opusHeard?: (said: Heard) => void;
		opusTv?: {
			/** leave the app altogether — the last thing back can mean. Older
			    wrappers do not have it, so it is asked for optionally. */
			quit?(): void;
			/** which build of the wrapper this is. Older wrappers do not answer. */
			version?(): number;
			engine(): string;
			probe(): string;
			/** what the picture goes into, as that device names itself over
			    HDMI; empty where Android cannot say. Older wrappers do not have it. */
			plugged?(): string;
			canVideo(codec: string, width: number, height: number): boolean;
			/** what is about to play or playing, for the box's own media session
			    — what the remote, the system and the house read. Older wrappers do
			    not have it. */
			describe?(title: string, artist: string, album: string, art: string): void;
			/** keep the screen from its screensaver while nothing plays on it
			    but a photograph is being shown. Older wrappers do not have it. */
			awake?(on: boolean): void;
			play(
				url: string,
				startSeconds: number,
				subs: string,
				audio: string,
				text: string,
				frameRate: number
			): void;
			toggle(): void;
			seek(seconds: number): void;
			stop(): void;
			captionsUp(raised: boolean): void;
			state(): string;
			chooseAudio(index: number): void;
			chooseText(index: number): void;
			/** Speech into the keyboard. Older wrappers do not have it. */
			hears?(): boolean;
			listen?(language: string): void;
			stopListening?(): void;
			voiceKey?(taken: boolean): void;
		};
	}
}

export {};
