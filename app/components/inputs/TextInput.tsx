import { Input } from '../../ui/input'
import { Label } from '../../ui/label'

interface TextInputProps {
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  placeholder?: string
  required?: boolean
}

export default function TextInput({ label, name, value, onChange, placeholder, required }: TextInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name} className="text-gray-700 font-medium">{label}</Label>
      <Input
        type="text"
        id={name}
        name={name}
        value={value}
        onChange={(e) => onChange(name, e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full bg-white text-gray-800 border-gray-300 focus:border-electric-blue focus:ring focus:ring-electric-blue focus:ring-opacity-50 transition-all duration-300"
      />
    </div>
  )
}

