import type { CSSProperties } from 'react';

interface IconProps {
  size?: number;
  style?: CSSProperties;
  'aria-hidden'?: boolean | 'true' | 'false';
}

const baseProps = (props: IconProps) => ({
  width: props.size ?? 18,
  height: props.size ?? 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  style: props.style,
  'aria-hidden': props['aria-hidden'] ?? true,
});

export function IconBank(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <path d="M3 21h18" />
      <path d="M3 10l9-6 9 6" />
      <path d="M5 21V11" />
      <path d="M19 21V11" />
      <path d="M9 21v-7" />
      <path d="M15 21v-7" />
    </svg>
  );
}

export function IconImport(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export function IconRobot(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <rect x="4" y="7" width="16" height="13" rx="2" />
      <path d="M12 3v4" />
      <circle cx="9" cy="13" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="15" cy="13" r="1.2" fill="currentColor" stroke="none" />
      <path d="M9 17h6" />
      <path d="M2 13h2" />
      <path d="M20 13h2" />
    </svg>
  );
}

export function IconMail(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <polyline points="3 7 12 13 21 7" />
    </svg>
  );
}

export function IconLock(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function IconUser(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
    </svg>
  );
}

export function IconAlert(props: IconProps) {
  return (
    <svg {...baseProps(props)}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}
