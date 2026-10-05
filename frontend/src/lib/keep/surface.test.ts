// @vitest-environment happy-dom
import { afterEach, expect, test, vi } from 'vitest';

afterEach(() => { vi.restoreAllMocks(); window.localStorage.clear(); });

test.each(['url', 'stored'])('Automatic keeps reacting after a %s startup override', async (source) => {
	vi.resetModules();
	window.history.replaceState({}, '', source === 'url' ? '/?surface=tv' : '/');
	if (source === 'stored') window.localStorage.setItem('opus.player.surface', 'tv');
	vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(1000);
	vi.spyOn(window, 'matchMedia').mockImplementation(() => ({ matches: false,
		addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as MediaQueryList);
	const { surface } = await import('./surface.svelte');
	surface.init();
	expect(surface.current).toBe('tv');
	surface.force(null);
	expect(surface.current).toBe('desktop');
	vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(500);
	window.dispatchEvent(new Event('resize'));
	expect(surface.current).toBe('mobile');
});
