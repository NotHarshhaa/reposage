import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "relative grid w-full grid-cols-[auto_1fr] gap-x-3 gap-y-1 border bg-card px-4 py-3 text-left text-sm border-l-2 [&>svg]:row-span-2 [&>svg]:mt-0.5 [&>svg]:size-4 [&>svg]:text-current",
  {
    variants: {
      variant: {
        default: "border-l-foreground text-card-foreground",
        destructive: "border-l-destructive text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return <div data-slot="alert" role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="alert-title" className={cn("col-start-2 text-sm font-semibold", className)} {...props} />
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="alert-description" className={cn("col-start-2 text-sm leading-5 text-muted-foreground", className)} {...props} />
}

function AlertAction({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="alert-action" className={cn("absolute top-2.5 right-3", className)} {...props} />
}

export { Alert, AlertTitle, AlertDescription, AlertAction }
