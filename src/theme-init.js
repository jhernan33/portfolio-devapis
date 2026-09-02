/**
 * TEMA — se aplica antes del primer pintado.
 * ==========================================
 *
 * Va aquí y no en main.js por una razón visible: main.js se carga con `defer`,
 * así que se ejecuta cuando el HTML ya está construido y el navegador ya ha
 * pintado la página con el tema claro. Quien tenía guardado el oscuro veía un
 * fogonazo blanco en cada carga.
 *
 * Este fichero se carga sin `defer` en el <head>: bloquea unos milisegundos,
 * pone el atributo y el primer pintado ya sale con el tema correcto.
 *
 * Define además la clave y las dos operaciones sobre ella, para que main.js no
 * tenga que repetir el nombre del almacén: dos literales iguales en dos
 * ficheros distintos son dos literales que acabarán siendo distintos.
 */
window.CVTema = (function () {
	'use strict';

	var CLAVE = 'cv-color-scheme';

	// localStorage lanza en modo privado de algunos navegadores y cuando el
	// usuario ha bloqueado el almacenamiento del sitio. El tema es una
	// comodidad: si no se puede leer ni guardar, se usa el del sistema y ya.
	function leer() {
		try {
			return localStorage.getItem(CLAVE);
		} catch (e) {
			return null;
		}
	}

	function guardar(valor) {
		try {
			localStorage.setItem(CLAVE, valor);
		} catch (e) {
			/* sin almacenamiento: el tema dura lo que la pestaña */
		}
	}

	function aplicar() {
		var guardado = leer();
		if (guardado) {
			document.documentElement.setAttribute('data-theme', guardado);
		}
	}

	aplicar();

	return { CLAVE: CLAVE, leer: leer, guardar: guardar, aplicar: aplicar };
})();
