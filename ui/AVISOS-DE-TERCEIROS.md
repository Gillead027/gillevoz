# Avisos de terceiros

Componentes de terceiros distribuídos com o GilleVoz e suas licenças.

## Tabler Icons — MIT

`@tabler/icons-react` (ícones da Flow Bar e do menu). O microfone animado em
`src/renderer/barra/Pecas.tsx` redesenha os traços do ícone `microphone` do Tabler.
Copyright (c) 2020-2024 Paweł Kuna. Licença MIT: https://github.com/tabler/tabler-icons/blob/main/LICENSE

## Motion — MIT

`motion` (molas e animações da Flow Bar). Copyright (c) 2018 Framer B.V.
Licença MIT: https://github.com/motiondivision/motion/blob/main/LICENSE.md

## Chakra Petch e Red Hat Mono — SIL Open Font License 1.1

Fontes locais via `@fontsource/chakra-petch` e `@fontsource/red-hat-mono`.

## Ideias de interação (sem código copiado)

Estas peças foram escritas do zero seguindo só a ideia/tempos descritos em `docs/REFERENCIAS-UI.md`;
nenhum arquivo ou trecho de código desses projetos foi copiado. Ficam registradas por cortesia:

- Morfose "ilha" da Flow Bar (`Barra.tsx`): Dynamic Island do cult-ui (MIT).
- Arco → ✓ (`Pecas.tsx`, `AnelProcessando`): Progress Ring Check do MicroKit (MIT).
- Destaque que desliza no menu (`menu/Menu.tsx`): Glide Select do React Bits (MIT + Commons Clause)
  e Glide Pill Tabs do MicroKit (MIT).
- Termômetro de LED (`Onda.tsx`): Voice Pill do React Bits + visualizador em matriz de LED (Inspora, só ideia).
- Hub (`src/renderer/hub/`), todas as peças escritas do zero:
  - Marcador do menu lateral e abas que deslizam (`Hub.tsx`, `pecas.tsx` `Segmentado`): Glide Pill Tabs do MicroKit (MIT).
  - Lista de escolha com destaque que desliza (`pecas.tsx` `Selecao`): Glide Select do React Bits (MIT + Commons Clause).
  - Keycaps (`pecas.tsx` `Teclas`): Kbd do Spell (MIT) e Raycast (via Refero, só ideia).
  - Números que rolam (`pecas.tsx` `NumeroRolando`): Count Up do MicroKit (MIT).
  - Apagar segurando (`pecas.tsx` `BotaoSegurar`): Hold to Delete do MicroKit (MIT).
  - Interruptor que estica (`pecas.tsx` `Interruptor`): Squish Switch do React Bits / Halo Switch do cult-ui (MIT).
  - Avisos que empilham e saem arrastando (`pecas.tsx` `Avisos`): Swipe Toast do React Bits / Halo Toast do cult-ui (MIT).
  - Busca com borda e brilho ao focar (`pecas.tsx` `Busca`): Focus Input do MicroKit (MIT).
