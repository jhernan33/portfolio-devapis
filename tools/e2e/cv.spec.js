// Tests de extremo a extremo del CV.
//
// El checklist manual de CLAUDE.md tenía seis puntos que nadie ejecutaba en
// cada cambio. Estos son esos seis puntos, automatizados. Comprueban lo que el
// resto de guardas no puede ver: que el JavaScript haga en un navegador de
// verdad lo que dice hacer.
const { test, expect } = require('@playwright/test');

// El tracking apunta a producción. Se intercepta siempre: un test no puede
// mandar visitas de mentira a las estadísticas reales.
test.beforeEach(async ({ page }) => {
	await page.route('https://devapis.cloud/api/track', (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"tracked"}' })
	);
});

test('el tema se cambia y sobrevive a la recarga', async ({ page }) => {
	await page.goto('./');
	const html = page.locator('html');

	await page.locator('#theme-toggle').click();
	const elegido = await html.getAttribute('data-theme');
	expect(['light', 'dark']).toContain(elegido);

	await page.reload();
	// Aplicado por theme-init.js, que corre sin defer: si esto fallara, el
	// visitante vería un fogonazo del tema contrario en cada carga.
	await expect(html).toHaveAttribute('data-theme', elegido);
});

test('el modal del certificado abre, atrapa el foco y lo devuelve al cerrar', async ({ page }) => {
	await page.goto('./');
	const tarjeta = page.locator('.cert-card[data-cert]').first();
	await tarjeta.click();

	const modal = page.locator('#cert-modal');
	await expect(modal).toBeVisible();
	await expect(page.locator('#cert-modal-img')).toHaveAttribute('src', /\.webp$/);

	// El foco no puede escaparse a la página de detrás: con lector de pantalla
	// se anunciaría contenido que visualmente está tapado.
	await page.keyboard.press('Tab');
	await expect(modal).toContainText(/./);
	const dentro = await page.evaluate(() =>
		document.getElementById('cert-modal').contains(document.activeElement)
	);
	expect(dentro).toBe(true);

	await page.keyboard.press('Escape');
	await expect(modal).toBeHidden();
	// Y vuelve a la tarjeta desde la que se abrió, no al principio del documento.
	await expect(tarjeta).toBeFocused();
});

test('las certificaciones colapsadas se despliegan y el botón lo dice', async ({ page }) => {
	await page.goto('./');
	const boton = page.locator('#certs-toggle');
	const extras = page.locator('.cert-card--extra');

	await expect(boton).toBeVisible();
	await expect(boton).toHaveText(/Ver \d+ certificaciones más/);
	await expect(extras.first()).toBeHidden();

	await boton.click();
	await expect(extras.first()).toBeVisible();
	await expect(boton).toHaveText('Ver menos');
});

test('la navegación marca la sección visible', async ({ page, isMobile }) => {
	await page.goto('./');

	// Por debajo de 768px los enlaces viven dentro del menú desplegable, así
	// que hay que abrirlo primero. Es el mismo recorrido que hace una persona.
	if (isMobile) await page.locator('#nav-toggle').tap();

	const enlace = page.locator('.nav__link[href="#proyectos"]').first();
	await enlace.click();

	await expect(enlace).toHaveClass(/nav__link--active/);
	await expect(page).toHaveURL(/#proyectos$/);

	// Al elegir destino el menú se cierra: dejarlo abierto tapa justo el
	// contenido al que se acaba de saltar.
	if (isMobile) await expect(page.locator('#nav')).toHaveAttribute('data-menu-open', 'false');
});

test('el tracking envía la ruta de la versión que se está viendo', async ({ page }) => {
	const enviados = [];
	await page.route('https://devapis.cloud/api/track', (route) => {
		enviados.push(route.request().postDataJSON());
		return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
	});

	await page.goto('en/');
	await expect.poll(() => enviados.length, { timeout: 5000 }).toBeGreaterThan(0);
	expect(enviados[0]).toEqual({ page: '/cv/en/' });
});

test('la versión inglesa no tiene texto en español en lo que genera el JS', async ({ page }) => {
	await page.goto('en/');
	await expect(page.locator('#certs-toggle')).toHaveText(/Show \d+ more certifications/);
	await page.locator('#nav-toggle').evaluate((b) => b.removeAttribute('hidden'));
	await expect(page.locator('#nav-toggle')).toHaveAttribute('aria-label', /Open navigation menu/);
});

test.describe('en móvil', () => {
	test.skip(({ isMobile }) => !isMobile, 'solo en el proyecto móvil');

	test('el menú se abre, navega y se cierra con Escape', async ({ page }) => {
		await page.goto('./');
		const nav = page.locator('#nav');
		const boton = page.locator('#nav-toggle');

		await expect(boton).toBeVisible();
		await boton.tap();
		await expect(nav).toHaveAttribute('data-menu-open', 'true');
		await expect(boton).toHaveAttribute('aria-expanded', 'true');

		await page.keyboard.press('Escape');
		await expect(nav).toHaveAttribute('data-menu-open', 'false');
	});

	test('un solo toque cambia el tema una sola vez', async ({ page }) => {
		// click y touchend llegan los dos: sin la guarda de onActivate, el tema
		// cambiaba y volvía en el mismo gesto.
		await page.goto('./');
		const html = page.locator('html');
		await page.locator('#theme-toggle').tap();
		const despues = await html.getAttribute('data-theme');
		expect(despues).toBe('dark');
	});
});
