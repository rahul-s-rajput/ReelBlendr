import * as React from "react"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'ghost'
  size?: 'default' | 'sm'
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background
          ${variant === 'default' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''}
          ${variant === 'ghost' ? 'hover:bg-accent hover:text-accent-foreground' : ''}
          ${size === 'default' ? 'h-10 py-2 px-4' : ''}
          ${size === 'sm' ? 'h-9 px-3 rounded-md' : ''}
          ${className}`}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

