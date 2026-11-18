import { cva, type VariantProps } from 'class-variance-authority'

export { default as Input } from './Input.vue'

export const inputVariants = cva(
  'w-full min-w-0 rounded-md border border-input bg-card text-foreground transition-colors placeholder:text-muted-foreground disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive',
  {
    variants: {
      size: {
        default: 'h-10 px-3 text-sm',
        // 高度 48 px
        lg: 'h-12 px-4 text-base',
      },
    },
    defaultVariants: { size: 'default' },
  },
)

export type InputVariants = VariantProps<typeof inputVariants>
