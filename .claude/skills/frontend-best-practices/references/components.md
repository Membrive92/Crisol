# Patrones de componentes compartidos (web/móvil)

## Tabla de contenidos
1. [Anatomía de un componente compartido](#anatomía-de-un-componente-compartido)
2. [Patrón de extensiones por plataforma](#patrón-de-extensiones-por-plataforma)
3. [Primitivos cross-platform](#primitivos-cross-platform)
4. [Composición y slots](#composición-y-slots)
5. [Estilos con NativeWind](#estilos-con-nativewind)
6. [Patrones prohibidos](#patrones-prohibidos)

---

## Anatomía de un componente compartido

Todo componente en `packages/ui/` sigue esta estructura:

```
Button/
├── Button.tsx           # Implementación principal
├── types.ts             # Interface de props
├── Button.test.tsx      # Tests unitarios
└── index.ts             # Re-export limpio
```

### types.ts — Props tipadas

```typescript
// packages/ui/src/components/Button/types.ts

import type { ReactNode } from 'react';

/**
 * Variantes visuales del botón.
 */
export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';

/**
 * Tamaños del botón.
 */
export type ButtonSize = 'sm' | 'md' | 'lg';

/**
 * Props del componente Button.
 * 
 * @example
 * ```tsx
 * <Button variant="primary" size="md" onPress={handleSubmit}>
 *   Guardar cambios
 * </Button>
 * ```
 */
export interface ButtonProps {
  /** Contenido del botón */
  children: ReactNode;
  /** Variante visual */
  variant?: ButtonVariant;
  /** Tamaño */
  size?: ButtonSize;
  /** Deshabilitado */
  disabled?: boolean;
  /** Estado de carga — muestra spinner y deshabilita interacción */
  loading?: boolean;
  /** Callback al presionar */
  onPress: () => void;
  /** Clases adicionales de Tailwind/NativeWind */
  className?: string;
  /** ID para testing */
  testID?: string;
}
```

### Button.tsx — Implementación

```tsx
// packages/ui/src/components/Button/Button.tsx

import { Pressable, Text, ActivityIndicator } from 'react-native';
import type { ButtonProps } from './types';

const VARIANT_STYLES: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-blue-600 active:bg-blue-700',
  secondary: 'bg-gray-600 active:bg-gray-700',
  outline: 'border border-gray-300 bg-transparent active:bg-gray-100',
  ghost: 'bg-transparent active:bg-gray-100',
  danger: 'bg-red-600 active:bg-red-700',
};

const SIZE_STYLES: Record<NonNullable<ButtonProps['size']>, string> = {
  sm: 'px-3 py-1.5',
  md: 'px-4 py-2.5',
  lg: 'px-6 py-3.5',
};

const TEXT_VARIANT_STYLES: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'text-white',
  secondary: 'text-white',
  outline: 'text-gray-800',
  ghost: 'text-gray-800',
  danger: 'text-white',
};

/**
 * Botón reutilizable cross-platform.
 * Renderiza correctamente en web (via react-native-web) y en móvil.
 */
export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onPress,
  className = '',
  testID,
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      testID={testID}
      className={`
        flex-row items-center justify-center rounded-lg
        ${VARIANT_STYLES[variant]}
        ${SIZE_STYLES[size]}
        ${isDisabled ? 'opacity-50' : ''}
        ${className}
      `}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={variant === 'outline' || variant === 'ghost' ? '#1f2937' : '#ffffff'}
        />
      ) : (
        <Text className={`font-semibold ${TEXT_VARIANT_STYLES[variant]}`}>
          {children}
        </Text>
      )}
    </Pressable>
  );
}
```

### index.ts — Re-export

```typescript
// packages/ui/src/components/Button/index.ts

export { Button } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './types';
```

---

## Patrón de extensiones por plataforma

Cuando un componente necesita implementaciones distintas por plataforma, 
usar extensiones de archivo:

```
ImagePicker/
├── ImagePicker.tsx          # Código compartido (si lo hay)
├── ImagePicker.web.tsx      # Implementación web (input file)
├── ImagePicker.native.tsx   # Implementación nativa (expo-image-picker)
├── types.ts                 # Props compartidas (SIEMPRE las mismas)
└── index.ts
```

**Regla crítica:** Ambas implementaciones DEBEN cumplir la misma interface de props.

```typescript
// types.ts
export interface ImagePickerProps {
  onImageSelected: (uri: string) => void;
  maxSizeMB?: number;
  allowedTypes?: Array<'image/jpeg' | 'image/png' | 'image/webp'>;
}
```

```tsx
// ImagePicker.web.tsx
import type { ImagePickerProps } from './types';

export function ImagePicker({ onImageSelected, maxSizeMB = 5 }: ImagePickerProps) {
  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > maxSizeMB * 1024 * 1024) return;
    onImageSelected(URL.createObjectURL(file));
  }

  return <input type="file" accept="image/*" onChange={handleFileChange} />;
}
```

```tsx
// ImagePicker.native.tsx
import * as ExpoImagePicker from 'expo-image-picker';
import { Pressable, Text } from 'react-native';
import type { ImagePickerProps } from './types';

export function ImagePicker({ onImageSelected }: ImagePickerProps) {
  async function handlePress() {
    const result = await ExpoImagePicker.launchImageLibraryAsync({
      mediaTypes: ExpoImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      onImageSelected(result.assets[0].uri);
    }
  }

  return (
    <Pressable onPress={handlePress}>
      <Text>Seleccionar imagen</Text>
    </Pressable>
  );
}
```

Metro (React Native) y webpack/Next.js resuelven automáticamente 
`.native.tsx` y `.web.tsx` respectivamente.

---

## Primitivos cross-platform

Crear wrappers primitivos que abstraigan diferencias básicas:

```typescript
// packages/ui/src/primitives/Text/AppText.tsx
import { Text as RNText } from 'react-native';
import type { TextProps as RNTextProps } from 'react-native';

type TextVariant = 'h1' | 'h2' | 'h3' | 'body' | 'caption' | 'label';

interface AppTextProps extends RNTextProps {
  variant?: TextVariant;
}

const VARIANT_CLASSES: Record<TextVariant, string> = {
  h1: 'text-3xl font-bold',
  h2: 'text-2xl font-semibold',
  h3: 'text-xl font-semibold',
  body: 'text-base',
  caption: 'text-sm text-gray-500',
  label: 'text-sm font-medium text-gray-700',
};

export function AppText({ variant = 'body', className = '', ...props }: AppTextProps) {
  return <RNText className={`${VARIANT_CLASSES[variant]} ${className}`} {...props} />;
}
```

Primitivos recomendados:
- `AppText` — Tipografía consistente
- `Box` — `View` con className (NativeWind ya lo soporta)
- `AppPressable` — Pressable con feedback visual estándar
- `Spacer` — Componente de espaciado explícito

---

## Composición y slots

Preferir composición con children y render props sobre configuración por props:

```tsx
// ❌ MAL — Configuración por props (rígido, difícil de extender)
<Card
  title="Perfil"
  subtitle="Información personal"
  icon={<UserIcon />}
  footer={<Button onPress={save}>Guardar</Button>}
/>

// ✅ BIEN — Composición con sub-componentes
<Card>
  <Card.Header>
    <Card.Icon><UserIcon /></Card.Icon>
    <Card.Title>Perfil</Card.Title>
    <Card.Subtitle>Información personal</Card.Subtitle>
  </Card.Header>
  <Card.Body>
    {/* Contenido flexible */}
  </Card.Body>
  <Card.Footer>
    <Button onPress={save}>Guardar</Button>
  </Card.Footer>
</Card>
```

Implementar sub-componentes con compound pattern:

```tsx
import { createContext, useContext, type ReactNode } from 'react';
import { View, Text } from 'react-native';

interface CardContextValue {
  variant: 'elevated' | 'outlined' | 'filled';
}

const CardContext = createContext<CardContextValue>({ variant: 'elevated' });

function CardRoot({ children, variant = 'elevated' }: { children: ReactNode; variant?: CardContextValue['variant'] }) {
  return (
    <CardContext.Provider value={{ variant }}>
      <View className="rounded-xl bg-white p-4 shadow-sm">{children}</View>
    </CardContext.Provider>
  );
}

function CardHeader({ children }: { children: ReactNode }) {
  return <View className="mb-3 flex-row items-center gap-3">{children}</View>;
}

function CardTitle({ children }: { children: ReactNode }) {
  return <Text className="text-lg font-semibold">{children}</Text>;
}

function CardBody({ children }: { children: ReactNode }) {
  return <View className="mb-3">{children}</View>;
}

function CardFooter({ children }: { children: ReactNode }) {
  return <View className="flex-row justify-end gap-2 border-t border-gray-100 pt-3">{children}</View>;
}

export const Card = Object.assign(CardRoot, {
  Header: CardHeader,
  Title: CardTitle,
  Body: CardBody,
  Footer: CardFooter,
});
```

---

## Estilos con NativeWind

### Reglas generales

- Usar clases de Tailwind/NativeWind como mecanismo principal de estilos.
- NUNCA usar StyleSheet.create en componentes compartidos — usar NativeWind.
- StyleSheet.create SOLO se permite en `apps/mobile/` para estilos que 
  NativeWind no pueda resolver.
- Variantes dinámicas con template literals o maps (como el ejemplo de Button).

### Responsive

```tsx
// NativeWind soporta breakpoints de Tailwind
<View className="flex-col md:flex-row gap-4">
  <View className="w-full md:w-1/2">{/* Sidebar */}</View>
  <View className="w-full md:w-1/2">{/* Content */}</View>
</View>
```

### Tema

Definir tokens de diseño en la config de Tailwind compartida:

```javascript
// packages/config/tailwind/tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '12px',
      },
    },
  },
};
```

---

## Patrones prohibidos

### ❌ NUNCA hacer

```tsx
// 1. Imports de plataforma en código compartido
import { useRouter } from 'next/navigation'; // ← PROHIBIDO en packages/

// 2. Detección de plataforma con condicionales
import { Platform } from 'react-native';
if (Platform.OS === 'web') { /* ... */ } // ← Usar .web.tsx/.native.tsx en su lugar

// 3. Props drilling profundo (>3 niveles)
<Screen user={user}>
  <Panel user={user}>
    <Section user={user}>
      <UserName user={user} /> // ← Usar Context o Zustand
    </Section>
  </Panel>
</Screen>

// 4. Lógica de negocio dentro de componentes UI
function ProductCard({ productId }: { productId: string }) {
  const product = useQuery(...); // ← La UI no hace fetch
  // packages/ui/ NUNCA hace data fetching
}

// 5. Estilos inline
<View style={{ marginTop: 20, backgroundColor: 'red' }} /> // ← Usar NativeWind
```

### ✅ En su lugar

```tsx
// 1. Inyección por props o extensiones de plataforma
// El componente recibe onNavigate como prop
<LoginForm onSuccess={navigateToHome} />

// 2. Extensiones de plataforma
// Button.web.tsx / Button.native.tsx

// 3. Context o store para datos profundos
const user = useUserStore((state) => state.currentUser);

// 4. Separar data fetching de presentación
// En apps/web o apps/mobile:
function ProductScreen() {
  const { data } = useProductQuery(productId);
  return <ProductCard product={data} />; // UI solo recibe datos
}

// 5. NativeWind
<View className="mt-5 bg-red-500" />
```
