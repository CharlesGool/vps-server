import { cva, type VariantProps } from 'class-variance-authority'

export { default as Textarea } from './Textarea.vue'

// 与 Input 同一套边框, 背景和焦点样式
export const textareaVariants = cva(
  'w-full min-w-0 resize-y rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted-foreground disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive',
  {
    variants: {
      size: {
        default: 'min-h-24',
        lg: 'min-h-40',
      },
    },
    defaultVariants: { size: 'default' },
  },
)

export type TextareaVariants = VariantProps<typeof textareaVariants>
