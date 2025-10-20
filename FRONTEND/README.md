# Meeting Analyzer - React Frontend

Una interfaz moderna y profesional para grabación y análisis de reuniones, construida con React, TypeScript y Tailwind CSS.

## 🚀 Características

### Grabador Profesional
- **Visualización de audio en tiempo real** con barras animadas
- **Control de grabación avanzado** (grabar, pausar, reanudar, detener)
- **Monitor de nivel de audio** en tiempo real
- **Gestión de participantes** con nombres y emails
- **Permisos de micrófono** con manejo de errores
- **Descarga de grabaciones** en formato WebM

### Análisis Inteligente
- **Visualización de resultados** con polling automático
- **Reproductor de audio integrado** con seek por timestamps
- **Puntos clave expandibles** con navegación temporal
- **Tabla de acciones y responsables**
- **Transcripción completa** con búsqueda y navegación
- **Exportación a PDF** y envío por email

### Base de Datos
- **Lista de reuniones** con filtros y búsqueda
- **Estados de procesamiento** en tiempo real
- **Gestión de reuniones** (renombrar, eliminar)
- **Filtros por fecha** y término de búsqueda

## 🛠️ Tecnologías

- **React 18** con TypeScript
- **Tailwind CSS** para estilos
- **Vite** como bundler
- **React Router** para navegación
- **Axios** para llamadas API
- **Lucide React** para iconos
- **MediaRecorder API** para grabación
- **Web Audio API** para análisis de audio

## 📦 Instalación

```bash
cd FRONTEND/react-recorder
npm install
```

## 🔧 Configuración

El proyecto está configurado para funcionar con el backend Flask en `localhost:5000`. La configuración de proxy en `vite.config.ts` redirige las llamadas API automáticamente.

### Variables de entorno

Crea un archivo `.env` si necesitas configuraciones específicas:

```env
VITE_API_BASE_URL=http://localhost:5000
```

## 🚀 Desarrollo

```bash
# Iniciar servidor de desarrollo
npm run dev

# El frontend estará disponible en http://localhost:3000
```

## 🏗️ Build para Producción

```bash
# Crear build de producción
npm run build

# Preview del build
npm run preview
```

## 📁 Estructura del Proyecto

```
src/
├── components/           # Componentes reutilizables
│   ├── Layout.tsx       # Layout principal con navegación
│   └── AudioVisualizer.tsx # Visualizador de audio profesional
├── pages/               # Páginas principales
│   ├── HomePage.tsx     # Página de inicio con opciones
│   ├── RecorderPage.tsx # Grabador profesional
│   ├── MeetingAnalysisPage.tsx # Análisis de reuniones
│   └── DatabasePage.tsx # Lista de reuniones
├── services/            # Servicios y utilidades
│   ├── api.ts          # Cliente API con endpoints
│   └── audioUtils.ts   # Utilidades de audio y grabación
├── types/              # Definiciones TypeScript
│   └── index.ts        # Tipos e interfaces
├── App.tsx             # Componente principal con routing
├── main.tsx            # Punto de entrada
└── index.css           # Estilos globales con Tailwind
```

## 🎯 Funcionalidades Principales

### 1. Grabación Profesional
- Visualización en tiempo real con barras de audio animadas
- Control completo de grabación (grabar/pausar/detener)
- Gestión de participantes antes y durante la grabación
- Descarga local y envío al servidor para análisis

### 2. Análisis Inteligente
- Polling automático para resultados en tiempo real
- Navegación por timestamps en audio
- Puntos clave expandibles con detalles
- Transcripción con búsqueda y highlighting

### 3. Gestión de Reuniones
- Lista completa con filtros y búsqueda
- Estados de procesamiento en tiempo real
- Operaciones CRUD (crear, leer, actualizar, eliminar)

## 🔗 Integración con Backend

El frontend está diseñado para integrarse perfectamente con el backend Flask:

### Endpoints Principales
- `POST /create_meeting_from_participants` - Crear reunión con participantes
- `POST /process_final_audio` - Subir audio grabado
- `GET /api/reunion/{id}` - Obtener detalles de reunión
- `GET /api/reuniones` - Listar reuniones
- `POST /upload_and_process_directly` - Subir y procesar audio directamente

### Flujo de Datos
1. **Grabación**: Crear reunión → Grabar audio → Subir para análisis
2. **Subida**: Subir archivo → Procesamiento automático → Visualización
3. **Análisis**: Polling de estado → Mostrar resultados → Interacción

## 🎨 Diseño y UX

### Principios de Diseño
- **Minimalista y moderno** con Tailwind CSS
- **Responsive** para todos los dispositivos
- **Feedback visual** para todas las acciones
- **Estados de carga** y manejo de errores
- **Animaciones suaves** para mejor UX

### Accesibilidad
- Contraste adecuado para legibilidad
- Navegación por teclado
- Aria labels para screen readers
- Estados de focus visibles

## 🔧 Personalización

### Colores
Los colores principales están definidos en `tailwind.config.js` y pueden personalizarse:

```js
colors: {
  primary: {
    // Personaliza los colores primarios aquí
  }
}
```

### Componentes
Todos los componentes están construidos con Tailwind CSS y son fácilmente personalizables modificando las clases CSS.

## 🐛 Solución de Problemas

### Problemas Comunes

1. **Error de permisos de micrófono**
   - Asegúrate de permitir acceso al micrófono en el navegador
   - Usa HTTPS en producción (requerido para MediaRecorder)

2. **API no responde**
   - Verifica que el backend Flask esté ejecutándose en `localhost:5000`
   - Revisa la configuración de proxy en `vite.config.ts`

3. **Audio no se reproduce**
   - Verifica que el archivo de audio exista en el servidor
   - Comprueba la configuración de CORS en el backend

## 🚀 Próximas Mejoras

- [ ] PWA (Progressive Web App) para instalación
- [ ] Modo offline con sincronización
- [ ] Temas claro/oscuro
- [ ] Shortcuts de teclado
- [ ] Arrastrar y soltar archivos
- [ ] Notificaciones push para estado de procesamiento
- [ ] Integración con calendarios
- [ ] Exportación a más formatos (Word, Excel)

## 📄 Licencia

Este proyecto forma parte del sistema Meeting Analyzer y sigue la misma licencia del proyecto principal.