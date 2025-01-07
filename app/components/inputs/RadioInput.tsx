import { Label } from '../../ui/label'
import { RadioGroup, RadioGroupItem } from '../../ui/radio-group'

interface RadioInputProps {
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  options: string[]
}

export default function RadioInput({ label, name, value, onChange, options }: RadioInputProps) {
  return (
    <div>
      <Label className="text-purple-200">{label}</Label>
      <RadioGroup value={value} onValueChange={(value) => onChange(name, value)} className="mt-2">
        {options.map((option) => (
          <div key={option} className="flex items-center space-x-2">
            <RadioGroupItem value={option} id={`${name}-${option}`} className="border-purple-500 text-purple-400" />
            <Label htmlFor={`${name}-${option}`} className="text-white">{option}</Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  )
}

