/**
 * CV PROFESIONAL - JavaScript
 * ============================
 * Funcionalidad mínima y esencial
 * Sin dependencias externas
 */

(function() {
	'use strict';

	/* ============================================
	   UTILIDADES COMPARTIDAS
	   ============================================ */

	/**
	 * Registra un manejador que responde igual al ratón y al dedo.
	 *
	 * En móvil, `touchend` llega antes que el `click` sintético que el
	 * navegador genera después, así que escuchar los dos disparaba la acción
	 * dos veces: el tema cambiaba y volvía. Se marca el tiempo del último
	 * disparo y se ignora lo que llegue en el medio segundo siguiente.
	 *
	 * Estaba copiado en cuatro módulos, cada uno con su propia versión de la
	 * misma idea. Aquí está escrito una vez.
	 */
	function onActivate(el, handler) {
		let ultimo = 0;
		const disparar = (e) => {
			const ahora = Date.now();
			if (ahora - ultimo < 500) return;
			ultimo = ahora;
			e.preventDefault();
			handler(e);
		};
		el.addEventListener('click', disparar);
		el.addEventListener('touchend', disparar, { passive: false });
	}

	/* ============================================
	   TEXTOS
	   ============================================ */

	/**
	 * Cadenas que genera el JavaScript, en los dos idiomas.
	 *
	 * `main.js` se comparte entre /cv y /cv/en, así que todo texto creado desde
	 * aquí tiene que seguir al idioma del documento. Estaba resuelto en cinco
	 * módulos con cinco ternarios `lang === 'en' ? ... : ...`, y bastaba con
	 * olvidar uno para que un lector de pantalla anunciara "Certificado Django"
	 * en la versión inglesa. Ahora el idioma se mira una vez y las cadenas
	 * viven juntas, donde se ve de un vistazo si falta alguna.
	 */
	const EN = document.documentElement.lang === 'en';

	const TEXTOS = {
		es: {
			menuAbrir: 'Abrir menú de navegación',
			menuCerrar: 'Cerrar menú de navegación',
			volverArriba: 'Volver arriba',
			certificado: 'Certificado',
			verificar: 'Verificar en Platzi',
			verMenos: 'Ver menos',
			verMas: (n) => `Ver ${n} certificaciones más`
		},
		en: {
			menuAbrir: 'Open navigation menu',
			menuCerrar: 'Close navigation menu',
			volverArriba: 'Back to top',
			certificado: 'Certificate',
			verificar: 'Verify on Platzi',
			verMenos: 'Show fewer',
			verMas: (n) => `Show ${n} more certifications`
		}
	};

	const t = (clave, ...args) => {
		const valor = TEXTOS[EN ? 'en' : 'es'][clave];
		return typeof valor === 'function' ? valor(...args) : valor;
	};

	/* ============================================
	   THEME TOGGLE (Light/Dark Mode)
	   ============================================ */
	
	const ThemeManager = {
		init() {
			this.toggle = document.getElementById('theme-toggle');
			if (!this.toggle) return;

			// El tema guardado ya lo aplicó theme-init.js antes del primer
			// pintado; aquí solo queda atender al botón.
			onActivate(this.toggle, () => this.switchTheme());
		},

		switchTheme() {
			const current = document.documentElement.getAttribute('data-theme');
			const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
			
			let next;
			if (current === 'dark') {
				next = 'light';
			} else if (current === 'light') {
				next = 'dark';
			} else {
				next = prefersDark ? 'light' : 'dark';
			}
			
			document.documentElement.setAttribute('data-theme', next);
			// La clave y el manejo de localStorage viven en theme-init.js, que
			// es quien tiene que conocerlos para aplicar el tema antes del
			// primer pintado. Aquí no se repiten.
			window.CVTema?.guardar(next);
			
			// Feedback visual para móvil
			if (this.toggle) {
				this.toggle.style.transform = 'scale(0.9)';
				setTimeout(() => {
					this.toggle.style.transform = '';
				}, 150);
			}
		}
	};

	/* ============================================
	   SMOOTH SCROLL
	   ============================================ */
	
	const SmoothScroll = {
		init() {
			document.querySelectorAll('a[href^="#"]').forEach(link => {
				link.addEventListener('click', (e) => {
					const href = link.getAttribute('href');
					if (href === '#') return;
					
					const target = document.querySelector(href);
					if (!target) return;
					
					e.preventDefault();
					target.scrollIntoView({ behavior: 'smooth', block: 'start' });
					history.pushState(null, '', href);
				});
			});
		}
	};

	/* ============================================
	   NAV ACTIVE STATE
	   ============================================ */
	
	const NavHighlight = {
		init() {
			this.links = document.querySelectorAll('.nav__link');
			this.sections = document.querySelectorAll('section[id]');
			
			if (!this.links.length || !this.sections.length) return;
			
			const observer = new IntersectionObserver(
				(entries) => this.handleIntersect(entries),
				{ rootMargin: '-20% 0px -60% 0px' }
			);
			
			this.sections.forEach(section => observer.observe(section));
		},
		
		handleIntersect(entries) {
			entries.forEach(entry => {
				if (entry.isIntersecting) {
					const id = entry.target.getAttribute('id');
					this.setActive(id);
				}
			});
		},
		
		setActive(id) {
			this.links.forEach(link => {
				const href = link.getAttribute('href');
				if (href === `#${id}`) {
					link.classList.add('nav__link--active');
				} else {
					link.classList.remove('nav__link--active');
				}
			});
		}
	};

	/* ============================================
	   ACCESSIBILITY
	   ============================================ */
	
	const Accessibility = {
		init() {
			// Skip link enhancement
			const skipLink = document.querySelector('.skip-link');
			if (skipLink) {
				skipLink.addEventListener('click', (e) => {
					e.preventDefault();
					const main = document.querySelector('#main');
					if (main) {
						main.focus();
						main.scrollIntoView({ behavior: 'smooth' });
					}
				});
			}
			
			// Announce live region for screen readers
			this.createLiveRegion();
		},
		
		createLiveRegion() {
			const region = document.createElement('div');
			region.setAttribute('aria-live', 'polite');
			region.setAttribute('aria-atomic', 'true');
			region.className = 'sr-only';
			document.body.appendChild(region);
			this.liveRegion = region;
		},
		
		announce(message) {
			if (this.liveRegion) {
				this.liveRegion.textContent = message;
			}
		}
	};

	/* ============================================
	   MOBILE MENU
	   ============================================ */

	/**
	 * Despliega la navegación por debajo de 768px.
	 *
	 * Ahí la lista de enlaces estaba oculta por CSS y no había nada en su
	 * lugar: quien entraba desde el móvil solo podía recorrer el CV entero a
	 * scroll. Dos de las siete visitas externas reales fueron móviles.
	 */
	const MobileMenu = {
		init() {
			this.nav = document.getElementById('nav');
			this.btn = document.getElementById('nav-toggle');
			this.menu = document.getElementById('nav-menu');
			if (!this.nav || !this.btn || !this.menu) return;

			this.btn.hidden = false;   // a partir de aquí lo gobierna el CSS

			onActivate(this.btn, () => this.toggle());

			// Al elegir destino el menú sobra: dejarlo abierto tapa el contenido
			// al que se acaba de saltar.
			this.menu.querySelectorAll('.nav__link').forEach(enlace => {
				enlace.addEventListener('click', () => this.cerrar());
			});

			document.addEventListener('keydown', (e) => {
				if (e.key === 'Escape' && this.abierto) {
					this.cerrar();
					this.btn.focus();
				}
			});

			// Tocar fuera cierra: en móvil no hay tecla Escape a mano.
			document.addEventListener('click', (e) => {
				if (this.abierto && !this.nav.contains(e.target)) this.cerrar();
			});

			// Al pasar a escritorio el menú vuelve a su sitio y el estado
			// abierto dejaría un panel flotante huérfano.
			window.addEventListener('resize', () => {
				if (window.innerWidth >= 768 && this.abierto) this.cerrar();
			});
		},

		get abierto() {
			return this.nav.dataset.menuOpen === 'true';
		},

		toggle() {
			this.abierto ? this.cerrar() : this.abrir();
		},

		abrir() {
			this.nav.dataset.menuOpen = 'true';
			this.btn.setAttribute('aria-expanded', 'true');
			this.btn.setAttribute('aria-label', t('menuCerrar'));
		},

		cerrar() {
			this.nav.dataset.menuOpen = 'false';
			this.btn.setAttribute('aria-expanded', 'false');
			this.btn.setAttribute('aria-label', t('menuAbrir'));
		}
	};

	/* ============================================
	   SCROLL TO TOP
	   ============================================ */

	/**
	 * Botón de volver arriba.
	 *
	 * Se crea desde JavaScript en lugar de venir en el HTML: sin script no
	 * tendría a qué recurrir, y creándolo aquí su etiqueta sigue al idioma del
	 * documento sin duplicarla en las dos versiones del CV.
	 */
	const ScrollTop = {
		UMBRAL: 600,

		init() {
			const btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'scroll-top';
			btn.setAttribute('aria-label', t('volverArriba'));

			const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
			svg.setAttribute('width', '20');
			svg.setAttribute('height', '20');
			svg.setAttribute('viewBox', '0 0 24 24');
			svg.setAttribute('fill', 'none');
			svg.setAttribute('stroke', 'currentColor');
			svg.setAttribute('stroke-width', '2');
			svg.setAttribute('aria-hidden', 'true');
			const linea = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
			linea.setAttribute('points', '18 15 12 9 6 15');
			svg.appendChild(linea);
			btn.appendChild(svg);

			document.body.appendChild(btn);
			this.btn = btn;

			btn.addEventListener('click', () => {
				// Respeta a quien ha pedido menos movimiento en su sistema: un
				// salto largo con animación puede provocar mareo.
				const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
				window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
				document.querySelector('.nav__logo')?.focus?.();
			});

			// passive: el listener no llama a preventDefault, y decírselo al
			// navegador evita que bloquee el hilo de scroll en cada evento.
			window.addEventListener('scroll', () => this.actualizar(), { passive: true });
			this.actualizar();
		},

		actualizar() {
			this.btn.classList.toggle('scroll-top--visible', window.scrollY > this.UMBRAL);
		}
	};

	/* ============================================
	   CERTIFICATE MODAL
	   ============================================ */
	
	const CertModal = {
		init() {
			this.modal = document.getElementById('cert-modal');
			this.modalImg = document.getElementById('cert-modal-img');
			this.modalTitle = document.getElementById('cert-modal-title');
			this.modalMeta = document.getElementById('cert-modal-meta');
			this.closeBtn = this.modal?.querySelector('.cert-modal__close');
			this.overlay = this.modal?.querySelector('.cert-modal__overlay');
			
			if (!this.modal) return;
			
			// Event listeners para abrir modal (cert-card en lugar de cert-thumb)
			document.querySelectorAll('.cert-card').forEach(card => {
				card.addEventListener('click', () => this.open(card));

				// Las tarjetas con diploma son <article>, que no entra en el
				// orden de tabulación ni se activa con Enter. Sin esto, el
				// modal era inalcanzable sin ratón. Las que son <a> ya lo
				// hacen solas, así que se excluyen.
				if (card.tagName === 'A' || !card.dataset.cert) return;
				card.tabIndex = 0;
				card.setAttribute('role', 'button');
				card.addEventListener('keydown', (e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						this.open(card);
					}
				});
			});
			
			// Event listeners para cerrar modal
			this.closeBtn?.addEventListener('click', () => this.close());
			this.overlay?.addEventListener('click', () => this.close());
			
			document.addEventListener('keydown', (e) => {
				if (e.key === 'Escape' && !this.modal.hidden) {
					this.close();
				}
				this.trapFocus(e);
			});
		},
		
		open(card) {
			const certSrc = card.dataset.cert;
			const certTitle = card.dataset.title;
			
			if (!certSrc) return;
			
			this.modalImg.src = certSrc;
			this.modalImg.alt = `${t('certificado')} ${certTitle}`;
			this.modalTitle.textContent = certTitle;
			this.renderMeta(card);

			// Se recuerda quién abrió el modal para devolverle el foco al
			// cerrarlo. Sin esto, quien navega con teclado o lector de pantalla
			// termina al principio del documento y tiene que recorrer la página
			// entera para volver a la tarjeta que estaba mirando.
			this.origen = document.activeElement;

			this.modal.hidden = false;
			document.body.style.overflow = 'hidden';
			this.closeBtn?.focus();
		},

		/**
		 * Mantiene el tabulador dentro del modal mientras está abierto.
		 *
		 * Un diálogo modal que deja escapar el foco a la página de detrás es
		 * confuso para cualquiera y directamente inutilizable con lector de
		 * pantalla: se anuncia contenido que visualmente está tapado.
		 */
		trapFocus(e) {
			if (e.key !== 'Tab' || this.modal.hidden) return;

			const focusables = this.modal.querySelectorAll(
				'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
			);
			if (!focusables.length) return;

			const primero = focusables[0];
			const ultimo = focusables[focusables.length - 1];

			if (e.shiftKey && document.activeElement === primero) {
				e.preventDefault();
				ultimo.focus();
			} else if (!e.shiftKey && document.activeElement === ultimo) {
				e.preventDefault();
				primero.focus();
			}
		},

		/**
		 * Emisor, fecha y código del diploma bajo la imagen, más el enlace de
		 * verificación cuando la tarjeta lo trae en data-verify.
		 *
		 * Se construye con createElement y textContent, nunca con innerHTML:
		 * es la misma disciplina que sigue el dashboard del backend, y aquí
		 * cuesta lo mismo aplicarla que saltársela.
		 */
		renderMeta(card) {
			if (!this.modalMeta) return;
			this.modalMeta.replaceChildren();

			const emisorFecha = card.querySelector('.cert-card__meta')?.textContent.trim();
			if (emisorFecha) {
				this.modalMeta.appendChild(document.createTextNode(emisorFecha));
			}

			// El código del diploma se conserva en data-code pero NO se muestra.
			// Platzi expone dos identificadores distintos —el impreso en el
			// diploma y el certId de su integración con LinkedIn— y en once de
			// los catorce certificados no coinciden. Con un enlace de
			// verificación de un clic, publicar un código que no se ha podido
			// contrastar añade riesgo sin añadir nada.

			// El enlace solo aparece si existe de verdad. Un "Verificar" que
			// lleva a ninguna parte es peor que no ofrecerlo: quien lo pulsa
			// pasa a dudar del certificado.
			const url = card.dataset.verify;
			if (url) {
				const enlace = document.createElement('a');
				enlace.className = 'cert-modal__verify';
				enlace.href = url;
				enlace.target = '_blank';
				enlace.rel = 'noopener';
				enlace.textContent = t('verificar');
				this.modalMeta.appendChild(enlace);
			}
		},
		
		close() {
			this.modal.hidden = true;
			document.body.style.overflow = '';
			// Devolver el foco a la tarjeta desde la que se abrió.
			this.origen?.focus?.();
			this.origen = null;
		}
	};

	/* ============================================
	   CERTS TOGGLE
	   ============================================ */

	/**
	 * Colapsa las certificaciones que no son destacadas.
	 *
	 * Diecinueve tarjetas de golpe, con seis de IA entre ellas, desplazan lo
	 * relevante en una vacante backend. Se muestran nueve y el resto queda tras
	 * un botón.
	 *
	 * El HTML llega con todas visibles y es este módulo el que las oculta. Al
	 * revés —ocultas por defecto, reveladas por JS— media sección desaparecería
	 * si el script fallara o el navegador lo bloqueara.
	 */
	const CertsToggle = {
		init() {
			this.grid = document.getElementById('certs-grid');
			this.btn = document.getElementById('certs-toggle');
			if (!this.grid || !this.btn) return;

			this.extras = this.grid.querySelectorAll('.cert-card--extra');
			if (!this.extras.length) return;

			// El número sale del DOM, no de una constante: si mañana cambia el
			// reparto entre destacadas y colapsadas, la etiqueta lo sigue sola.
			this.btn.hidden = false;
			this.render();

			onActivate(this.btn, () => this.toggle());
		},

		get expandido() {
			return this.grid.dataset.expanded === 'true';
		},

		render() {
			this.btn.textContent = this.expandido
				? t('verMenos')
				: t('verMas', this.extras.length);
			this.btn.setAttribute('aria-expanded', String(this.expandido));
		},

		toggle() {
			this.grid.dataset.expanded = String(!this.expandido);
			this.render();
			// Al colapsar, devolver el foco al botón: si no, el lector de
			// pantalla se queda anclado a una tarjeta que acaba de ocultarse.
			if (!this.expandido) this.btn.focus();
		}
	};

	/* ============================================
	   IMPRESIÓN
	   ============================================ */

	// El botón del nav ya no imprime: descarga el CV en formato ATS. Aquí solo
	// queda la impresión de la propia página (Ctrl+P o el menú del navegador),
	// que en tema oscuro saldría con el fondo negro.
	//
	// Se escucha beforeprint/afterprint en lugar de interceptar Ctrl+P: así
	// también cubre el menú del navegador y la vista previa, y desaparece el
	// window.print() diferido con setTimeout, que era una carrera contra el
	// repintado.
	const PrintHandler = {
		init() {
			this.temaPrevio = null;

			window.addEventListener('beforeprint', () => {
				this.temaPrevio = document.documentElement.getAttribute('data-theme');
				document.documentElement.setAttribute('data-theme', 'light');
			});

			window.addEventListener('afterprint', () => {
				if (this.temaPrevio) {
					document.documentElement.setAttribute('data-theme', this.temaPrevio);
				} else {
					document.documentElement.removeAttribute('data-theme');
				}
				this.temaPrevio = null;
			});
		}
	};

	/* ============================================
	   ANALYTICS TRACKER
	   ============================================ */

	const Analytics = {
		init() {
			// Esperar un momento antes de trackear para evitar false positives
			setTimeout(() => {
				this.trackVisit();
			}, 1000);
		},

		async trackVisit() {
			try {
				// Se envía la ruta para poder distinguir el CV en español del
				// inglés. Sin esto no había forma de saber si la versión
				// traducida, que se genera y se mantiene, la lee alguien.
				// El backend no la guarda en crudo: la compara contra una
				// lista cerrada y lo que no reconoce lo registra como "otro".
				const response = await fetch('https://devapis.cloud/api/track', {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json'
					},
					body: JSON.stringify({ page: window.location.pathname }),
					credentials: 'omit'
				});

				await response.json();
			} catch (error) {
				// Silenciar errores de analytics para no afectar UX
				console.debug('Analytics tracking failed:', error.message);
			}
		}
	};

	/* ============================================
	   INIT
	   ============================================ */
	
	function init() {
		// Lo primero, antes de cualquier módulo: hay CSS que depende de este
		// atributo (las certificaciones colapsadas). Marcarlo al final dejaba
		// un parpadeo en el que se veían las diecinueve tarjetas y acto seguido
		// se plegaban.
		document.documentElement.setAttribute('data-js', 'true');

		ThemeManager.init();
		SmoothScroll.init();
		NavHighlight.init();
		Accessibility.init();
		MobileMenu.init();
		ScrollTop.init();
		CertModal.init();
		CertsToggle.init();
		PrintHandler.init();
		Analytics.init();
	}

	// Run on DOM ready
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}

})();
