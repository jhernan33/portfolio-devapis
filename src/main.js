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
	   PDF EXPORT
	   ============================================ */

	const PDFExport = {
		init() {
			this.btn = document.getElementById('export-pdf');
			if (!this.btn) {
				console.warn('PDF export button not found');
				return;
			}
			
			console.log('PDF export button found');
			
			// Usar tanto click como touchend para mejor compatibilidad móvil
			this.btn.addEventListener('click', (e) => {
				console.log('PDF button clicked');
				e.preventDefault();
				this.exportPDF();
			});
			
			this.btn.addEventListener('touchend', (e) => {
				console.log('PDF button touched');
				e.preventDefault();
				this.exportPDF();
			}, { passive: false });
		},
		
		exportPDF() {
			// Forzar tema claro para impresión
			const currentTheme = document.documentElement.getAttribute('data-theme');
			document.documentElement.setAttribute('data-theme', 'light');
			
			// Pequeño delay para que se apliquen los estilos
			setTimeout(() => {
				window.print();
				
				// Restaurar tema después de imprimir
				if (currentTheme) {
					document.documentElement.setAttribute('data-theme', currentTheme);
				} else {
					document.documentElement.removeAttribute('data-theme');
				}
			}, 100);
		}
	};

	/* ============================================
	   PRINT HANDLER
	   ============================================ */

	const PrintHandler = {
		init() {
			document.addEventListener('keydown', (e) => {
				if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
					e.preventDefault();
					PDFExport.exportPDF();
				}
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
		CertModal.init();
		CertsToggle.init();
		PDFExport.init();
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
