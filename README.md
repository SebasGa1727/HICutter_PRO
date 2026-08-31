# HICutter (Historical Image Cutter)

## Descripción General

**HICutter** es una aplicación de escritorio de alto rendimiento diseñada para la optimización, conversión y procesamiento masivo de archivos digitales (imágenes y documentos). Construida sobre Python, la herramienta está específicamente orientada a flujos de trabajo intensivos, como la digitalización de archivos históricos, donde la velocidad de procesamiento, la gestión eficiente de la memoria RAM y la precisión son críticas.

El sistema integra algoritmos de visión computacional y modelos de inteligencia artificial para automatizar flujos de trabajo complejos, manteniendo siempre la posibilidad de intervención humana para el control de calidad.

## Características Principales

* **Procesamiento e Ingesta de Formatos Pesados (RAW/TIFF):** Motor de conversión directa de formatos sin pérdida (RAW, TIFF) a JPG. Incluye un módulo de organización estructurada y la aplicación de filtros de procesamiento de imagen integrados.

* **Procesamiento por Lotes de Ultra Alta Velocidad:** Pipeline de ejecución optimizado para imágenes JPG y PNG. El motor de procesamiento masivo gestiona dinámicamente los recursos del sistema, optimizando el uso de la memoria RAM y los ciclos de CPU para garantizar tiempos de ejecución mínimos en lotes de gran volumen.

* **Recorte Inteligente Asistido por IA (YOLO):** Implementación de inferencia de modelos de *Deep Learning* (Ultralytics YOLO) para la detección y recorte automatizado de elementos en las imágenes.

  * *Módulo de Control de Calidad (QC):* El sistema segrega automáticamente las inferencias con métricas de baja confianza, enviándolas a una cola de validación manual para revisión por parte de operadores humanos, asegurando una precisión del 100% en el dataset final.

* **Conversión Masiva de PDF Optimizada:** Motor de extracción y conversión de documentos PDF por lotes. Su arquitectura minimiza las operaciones de lectura y escritura (I/O) en el disco físico, procesando flujos de datos en memoria para alcanzar velocidades de conversión excepcionales.

## Stack Tecnológico

La arquitectura de HICutter se fundamenta en las siguientes tecnologías e integraciones:

* **Lenguaje Core:** Python 3.x

* **Interfaz Gráfica (GUI):** PyQt6 (Framework robusto para aplicaciones de escritorio escalables).

* **Visión Computacional:** OpenCV (Procesamiento matricial de imágenes, filtros y transformaciones eficientes).

* **Inteligencia Artificial:** Ultralytics YOLO (Arquitectura de redes neuronales convolucionales para detección de objetos en tiempo real).