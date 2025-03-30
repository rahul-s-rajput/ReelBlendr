import { Input } from '../../ui/input'
import { Label } from '../../ui/label'
import { Slider } from '../../ui/slider'
import { ReactNode } from 'react'

interface NumberInputProps {
  label: ReactNode
  name: string
  value: number
  onChange: (name: string, value: number) => void
  min: number
  max: number
  step: number
}

export default function NumberInput({ label, name, value, onChange, min, max, step }: NumberInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name} className="text-gray-700 font-medium">{label}</Label>
      <div className="flex items-center space-x-4">
        <Slider
          id={name}
          min={min}
          max={max}
          step={step}
          value={[value]}
          onValueChange={(newValue) => onChange(name, newValue[0])}
          className="flex-grow"
        />
        <Input
          type="number"
          id={`${name}-input`}
          name={name}
          value={value}
          onChange={(e) => onChange(name, parseInt(e.target.value))}
          min={min}
          max={max}
          step={step}
          className="w-20 bg-white text-gray-800 border-gray-300 focus:border-electric-blue focus:ring focus:ring-electric-blue focus:ring-opacity-50"
        />
      </div>
    </div>
  )
}

