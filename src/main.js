/**
 * CV PROFESIONAL - JavaScript
 * ============================
 * Funcionalidad mínima y esencial
 * Sin dependencias externas
 */

(function() {
	'use strict';

	/* ============================================
	   THEME TOGGLE (Light/Dark Mode)
	   ============================================ */
	
	const ThemeManager = {
		STORAGE_KEY: 'cv-color-scheme',
		
		init() {
			this.toggle = document.getElementById('theme-toggle');
			if (!this.toggle) {
				console.warn('Theme toggle button not found');
				return;
			}
			
			console.log('Theme toggle button found');
			this.loadTheme();
			
			// Usar tanto click como touchend para mejor compatibilidad móvil
			this.toggle.addEventListener('click', (e) => {
				console.log('Theme toggle clicked');
				e.preventDefault();
				this.switchTheme();
			});
			
			this.toggle.addEventListener('touchend', (e) => {
				console.log('Theme toggle touched');
				e.preventDefault();
				this.switchTheme();
			}, { passive: false });
		},
		
		loadTheme() {
			const saved = localStorage.getItem(this.STORAGE_KEY);
			if (saved) {
				document.documentElement.setAttribute('data-theme', saved);
			}
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
			localStorage.setItem(this.STORAGE_KEY, next);
			
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

			this.en = document.documentElement.lang === 'en';
			this.btn.hidden = false;   // a partir de aquí lo gobierna el CSS

			const alternar = (e) => {
				e.preventDefault();
				this.toggle();
			};
			this.btn.addEventListener('click', alternar);
			this.btn.addEventListener('touchend', alternar);

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
			this.btn.setAttribute('aria-label', this.en ? 'Close navigation menu' : 'Cerrar menú de navegación');
		},

		cerrar() {
			this.nav.dataset.menuOpen = 'false';
			this.btn.setAttribute('aria-expanded', 'false');
			this.btn.setAttribute('aria-label', this.en ? 'Open navigation menu' : 'Abrir menú de navegación');
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
			const en = document.documentElement.lang === 'en';
			const btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'scroll-top';
			btn.setAttribute('aria-label', en ? 'Back to top' : 'Volver arriba');

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
			// main.js se comparte entre /cv y /cv/en, así que el texto que se
			// genera desde aquí tiene que seguir al idioma del documento. Con
			// la cadena fija en español, un lector de pantalla en la versión
			// inglesa anunciaba "Certificado Django".
			const en = document.documentElement.lang === 'en';
			const certLabel = en ? 'Certificate' : 'Certificado';
			this.modalImg.alt = `${certLabel} ${certTitle}`;
			this.modalTitle.textContent = certTitle;
			this.renderMeta(card, en);

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
		renderMeta(card, en) {
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
				enlace.textContent = en ? 'Verify on Platzi' : 'Verificar en Platzi';
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
			this.en = document.documentElement.lang === 'en';
			this.btn.hidden = false;
			this.render();

			const alternar = (e) => {
				e.preventDefault();
				this.toggle();
			};
			this.btn.addEventListener('click', alternar);
			this.btn.addEventListener('touchend', alternar);
		},

		get expandido() {
			return this.grid.dataset.expanded === 'true';
		},

		render() {
			const n = this.extras.length;
			this.btn.textContent = this.expandido
				? (this.en ? 'Show fewer' : 'Ver menos')
				: (this.en ? `Show ${n} more certifications` : `Ver ${n} certificaciones más`);
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
				const response = await fetch('https://devapis.cloud/api/track', {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json'
					},
					credentials: 'omit'
				});

				if (response.ok) {
					const data = await response.json();
					console.log('✅ Visit tracked:', data.timestamp);
				}
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
		console.log('CV JS initialized');

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

		console.log('All modules loaded');
	}

	// Run on DOM ready
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}

})();
