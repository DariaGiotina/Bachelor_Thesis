// Building blocks that mirror the components of the Figma design (Button, Field, Chip, Checkbox,
// Radio, Segmented, list rows, callouts) so every screen is assembled from the same parts.
import { router } from 'expo-router';
import { ReactNode, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, fonts, pastel, PastelName, radius, type } from '@/lib/theme';
import { Icon, IconName } from './icon';

// ------------------------------------------------------------------ layout

/** Screen with the cream canvas, an optional nav bar, scrolling content and a pinned footer. */
export function Screen({
  children,
  footer,
  nav,
  dark = false,
  scroll = true,
  inTabs = false,
  contentStyle,
}: {
  children: ReactNode;
  footer?: ReactNode;
  nav?: ReactNode;
  dark?: boolean;
  scroll?: boolean;
  /** inside the tab navigator the tab bar already keeps clear of the bottom edge */
  inTabs?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
}) {
  const bg = dark ? colors.night : colors.canvas;
  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.content, contentStyle]}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}>
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.content, { flex: 1 }, contentStyle]}>{children}</View>
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: bg }} edges={inTabs ? ['top'] : ['top', 'bottom']}>
      {nav}
      {body}
      {footer ? <View style={[styles.footer, { backgroundColor: bg }]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

export function NavBar({
  title,
  right,
  onBack,
  light = false,
  backIcon = 'chevron-left',
}: {
  title?: string;
  right?: ReactNode;
  onBack?: () => void;
  light?: boolean;
  backIcon?: IconName;
}) {
  const tint = light ? colors.white : colors.ink;
  return (
    <View style={styles.nav}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Back"
        hitSlop={8}
        style={styles.navAction}
        onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))}>
        <Icon name={backIcon} color={tint} />
      </Pressable>
      <Text style={[type.bodyStrong, { color: tint }]} numberOfLines={1}>
        {title ?? ''}
      </Text>
      <View style={[styles.navAction, { alignItems: 'flex-end' }]}>{right}</View>
    </View>
  );
}

export function Heading({ title, subtitle, large = false }: { title: string; subtitle?: string; large?: boolean }) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={large ? type.display : type.title} accessibilityRole="header">
        {title}
      </Text>
      {subtitle ? <Text style={type.bodyL}>{subtitle}</Text> : null}
    </View>
  );
}

export function Section({ title, action, onAction, children }: { title: string; action?: string; onAction?: () => void; children: ReactNode }) {
  return (
    <View style={{ gap: 12 }}>
      <View style={styles.sectionHeader}>
        <Text style={type.section}>{title}</Text>
        {action ? (
          <Text style={[type.label, { color: colors.accent }]} onPress={onAction} suppressHighlighting>
            {action}
          </Text>
        ) : null}
      </View>
      {children}
    </View>
  );
}

// ------------------------------------------------------------------ controls

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
  icon,
  compact = false,
}: {
  label: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  icon?: IconName;
  compact?: boolean;
}) {
  const fg = variant === 'primary' ? colors.white : variant === 'ghost' ? colors.accent : colors.ink;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        compact && { height: 44 },
        variant === 'primary' && { backgroundColor: colors.accent },
        variant === 'secondary' && { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
        (disabled || loading) && { opacity: 0.5 },
        pressed && { opacity: 0.85 },
      ]}>
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Icon name={icon} size={20} color={fg} /> : null}
      <Text style={[type.button, { color: fg }]}>{label}</Text>
    </Pressable>
  );
}

export function Field({
  label,
  error,
  hint,
  ...input
}: TextInputProps & { label: string; error?: string | null; hint?: ReactNode }) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Text style={type.label}>{label}</Text>
      <TextInput
        placeholderTextColor={colors.ink3}
        {...input}
        onFocus={(e) => {
          setFocused(true);
          input.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          input.onBlur?.(e);
        }}
        style={[
          styles.input,
          focused && { borderColor: colors.accent, borderWidth: 1.5 },
          !!error && { borderColor: colors.flag, borderWidth: 1.5 },
        ]}
      />
      {error ? <Text style={[type.caption, { color: colors.flag }]}>{error}</Text> : hint}
    </View>
  );
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={() => onChange(!checked)}
      style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
      <View style={[styles.checkbox, checked ? { backgroundColor: colors.accent, borderWidth: 0 } : null]}>
        {checked ? <Icon name="check" size={18} color={colors.white} /> : null}
      </View>
      <View style={{ flex: 1 }}>{typeof label === 'string' ? <Text style={type.body}>{label}</Text> : label}</View>
    </Pressable>
  );
}

export function Radio({ selected }: { selected: boolean }) {
  return (
    <View
      style={[
        styles.radio,
        selected ? { borderColor: colors.accent, borderWidth: 6 } : { borderColor: colors.ink3, borderWidth: 1.5 },
      ]}
    />
  );
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && { backgroundColor: colors.tint, borderColor: colors.accent }]}>
      <Text style={[type.label, { color: selected ? colors.accentDeep : colors.ink }]}>{label}</Text>
    </Pressable>
  );
}

export function ChipGroup({ children }: { children: ReactNode }) {
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{children}</View>;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <View style={styles.segmented}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable
            key={o.value}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            onPress={() => onChange(o.value)}
            style={[styles.segment, on && { backgroundColor: colors.surface }]}>
            <Text style={on ? type.bodyStrong : type.label}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ------------------------------------------------------------------ content blocks

export function Callout({ children, icon = 'info', tone = 'rose' }: { children: ReactNode; icon?: IconName; tone?: 'rose' | 'caution' | 'flag' }) {
  const bg = tone === 'caution' ? colors.cautionTint : tone === 'flag' ? colors.flagTint : colors.tint;
  const ink = tone === 'caution' ? colors.caution : tone === 'flag' ? colors.flag : colors.accent;
  return (
    <View style={[styles.callout, { backgroundColor: bg }]}>
      <Icon name={icon} color={ink} />
      <View style={{ flex: 1, gap: 4 }}>{typeof children === 'string' ? <Text style={[type.label, { color: colors.ink }]}>{children}</Text> : children}</View>
    </View>
  );
}

export function List({ children }: { children: ReactNode }) {
  return <View style={styles.list}>{children}</View>;
}

export function Divider({ inset = 16 }: { inset?: number }) {
  return <View style={{ height: 1, marginLeft: inset, backgroundColor: colors.line }} />;
}

export function IconTile({ name, tone = 'rose', size = 40 }: { name: IconName; tone?: PastelName; size?: number }) {
  return (
    <View style={[styles.iconTile, { width: size, height: size, borderRadius: size / 3, backgroundColor: pastel[tone].bg }]}>
      <Icon name={name} size={size * 0.55} color={pastel[tone].ink} />
    </View>
  );
}

export function Row({
  title,
  subtitle,
  left,
  right,
  onPress,
  highlighted = false,
}: {
  title: string;
  subtitle?: string;
  left?: ReactNode;
  right?: ReactNode;
  onPress?: () => void;
  highlighted?: boolean;
}) {
  const body = (
    <>
      {left}
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={type.bodyStrong}>{title}</Text>
        {subtitle ? <Text style={type.label}>{subtitle}</Text> : null}
      </View>
      {right}
    </>
  );
  const style = [styles.row, highlighted && { backgroundColor: colors.tint }];
  // A disabled Pressable would also disable controls placed in `right` (e.g. a switch) on web.
  if (!onPress) return <View style={style}>{body}</View>;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={style}>
      {body}
    </Pressable>
  );
}

export function Pill({ label, tone = 'rose' }: { label: string; tone?: PastelName }) {
  return (
    <View style={[styles.pill, { backgroundColor: pastel[tone].bg }]}>
      <Text style={[type.caption, { color: pastel[tone].ink }]}>{label}</Text>
    </View>
  );
}

export function Bar({ value, color = colors.accent, track = colors.tintStrong }: { value: number; color?: string; track?: string }) {
  return (
    <View style={{ height: 4, borderRadius: 2, backgroundColor: track, overflow: 'hidden', flex: 1 }}>
      <View style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, height: 4, backgroundColor: color }} />
    </View>
  );
}

export function StepNumber({ n, tone = 'rose' }: { n: number; tone?: PastelName }) {
  return (
    <View style={[styles.stepNumber, { backgroundColor: pastel[tone].bg }]}>
      <Text style={[type.bodyStrong, { color: pastel[tone].ink }]}>{n}</Text>
    </View>
  );
}

export function Logo() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Icon name="bow" size={24} color={colors.accent} />
      <Text style={{ fontFamily: fonts.serif, fontSize: 20, color: colors.ink }}>Lumière</Text>
    </View>
  );
}

export function TextLink({ children, onPress }: { children: string; onPress: () => void }) {
  return (
    <Text style={[type.bodyStrong, { color: colors.accent }]} onPress={onPress} suppressHighlighting accessibilityRole="link">
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 28 },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8, gap: 10 },
  nav: { height: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12 },
  navAction: { width: 56, height: 40, justifyContent: 'center' },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  button: {
    height: 52,
    borderRadius: radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 20,
  },
  input: {
    height: 52,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 16,
    fontFamily: fonts.regular,
    fontSize: 17,
    color: colors.ink,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.ink3,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 0,
  },
  radio: { width: 22, height: 22, borderRadius: 11, backgroundColor: colors.surface },
  chip: {
    height: 38,
    paddingHorizontal: 14,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    justifyContent: 'center',
  },
  segmented: { flexDirection: 'row', gap: 4, padding: 4, borderRadius: 12, backgroundColor: colors.tint },
  segment: { flex: 1, height: 36, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  callout: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: radius.md },
  list: { backgroundColor: colors.surface, borderRadius: radius.lg, overflow: 'hidden' },
  iconTile: { alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, alignSelf: 'flex-start' },
  stepNumber: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
});
