import uuid
from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from acervo.forms import ProdutoForm
from acervo.models import Produto
from acervo.services import salvar_produto
from .musicbrainz import pesquisar, FonteIndisponivel
from .dvd_dataset import pesquisar as pesquisar_filmes

class PesquisaForm(forms.Form):
    q = forms.CharField(label='Álbum ou título', required=False, max_length=200)
    artista = forms.CharField(required=False, max_length=200)
    ean = forms.CharField(label='EAN/UPC', required=False, max_length=20)
    fonte = forms.ChoiceField(choices=[('musicbrainz', 'MusicBrainz — CDs'), ('movies', 'Base local do grupo — DVDs')])
    ano = forms.IntegerField(required=False, min_value=1)
    externa = forms.BooleanField(label='Consultar fonte mesmo com produto local encontrado', required=False)


def metadados(request):
    produto = get_object_or_404(Produto, pk=request.GET['produto']) if request.GET.get('produto') else None
    pesquisa = PesquisaForm(request.GET or None)
    results = []
    erro = None
    product_form = None
    locais = Produto.objects.none()
    choices = request.session.get('metadados_escolhas', {})
    choice_key = request.POST.get('escolha', '')
    if request.method == 'POST':
        choice = choices.get(choice_key)
        if choice is None:
            erro = 'Seleção expirada. Pesquise novamente.'
        elif request.POST.get('acao') == 'salvar':
            product_form = ProdutoForm(request.POST, instance=produto)
            if product_form.is_valid():
                if product_form.cleaned_data['tipo'] != choice['tipo']:
                    product_form.add_error('tipo', 'Tipo incompatível com a fonte selecionada.')
                else:
                    obj = product_form.save(commit=False)
                    obj.identificadores = {**obj.identificadores, **choice['identificadores']}
                    obj.metadados = {**obj.metadados, **choice['metadados']}
                    obj.origem = choice['origem']
                    try:
                        obj = salvar_produto(obj, request.user)
                        request.session.pop('metadados_escolhas', None)
                        return redirect('/acervo/cadastrar/?produto=' + str(obj.pk))
                    except (ValidationError, IntegrityError):
                        product_form.add_error(None, 'Dados inválidos ou produto já cadastrado. Confira o EAN.')
        else:
            initial = {k: v for k, v in choice.items() if k in ProdutoForm.Meta.fields}
            if produto:
                initial['categoria'] = produto.categoria_id
                initial['ean'] = produto.ean
            product_form = ProdutoForm(instance=produto, initial=initial)
    elif pesquisa.is_valid():
        data = pesquisa.cleaned_data
        if data['q'] or data['ean']:
            filtro = Q()
            if data['q']:
                filtro |= Q(titulo__icontains=data['q'])
            if data['ean']:
                filtro |= Q(ean=data['ean'])
            locais = Produto.objects.filter(filtro)[:20]
        try:
            if produto or data['externa'] or not locais:
                if data['ean']:
                    results = pesquisar_filmes(ean=data['ean'])
                if not results:
                    results = pesquisar(data['q'], data['artista'], data['ean']) if data['fonte'] == 'musicbrainz' else pesquisar_filmes(data['q'], data['ano'], data['ean'])
            choices = {uuid.uuid4().hex: row for row in results}
            request.session['metadados_escolhas'] = choices
        except FonteIndisponivel as exc:
            choices = {}
            request.session.pop('metadados_escolhas', None)
            erro = str(exc)
    return render(request, 'acervo/metadados.html', {'pesquisa': pesquisa, 'results': choices.items() if request.method == 'GET' else [],
        'erro': erro, 'product_form': product_form, 'escolha': choice_key, 'produto': produto, 'locais': locais})


class BuscaCDForm(forms.Form):
    codigo = forms.RegexField(r'^(?:[0-9]{8}|[0-9]{12}|[0-9]{13})$', widget=forms.HiddenInput)
    titulo = forms.CharField(label='Título do álbum', required=False, max_length=200)
    artista = forms.CharField(label='Artista', required=False, max_length=200)

    def clean(self):
        data = super().clean()
        if max(sum(c.isalnum() for c in data.get(k, '')) for k in ('titulo', 'artista')) < 2:
            raise forms.ValidationError('Informe um título ou artista com pelo menos dois caracteres úteis.')
        return data


def buscar_cd(request):
    from acervo.barcode_flow import codigo_comercial, cadastro_manual_url, guardar_prefill
    from acervo.models import Exemplar
    codigo = request.GET.get('codigo', '').strip()
    # Revalidar a prioridade local mesmo quando o endereço for aberto diretamente.
    if not codigo_comercial(codigo):
        return redirect('codigo_barras')
    if (Produto.objects.filter(ean=codigo).exists() or
            Exemplar.objects.filter(codigo_interno=codigo).exists() or pesquisar_filmes(ean=codigo)):
        from django.urls import reverse
        from urllib.parse import urlencode
        return redirect(reverse('codigo_barras') + '?' + urlencode({'codigo': codigo}))
    submitted = 'titulo' in request.GET or 'artista' in request.GET
    form = BuscaCDForm(request.GET if submitted else None, initial={'codigo': codigo})
    results, erro = [], None
    if submitted and form.is_valid():
        try:
            rows = pesquisar(form.cleaned_data['titulo'], form.cleaned_data['artista'])
            for row in rows:
                fields = {**row, 'ean': codigo}
                results.append({**row, 'cadastro_url': guardar_prefill(request, fields, codigo)})
        except FonteIndisponivel as exc:
            erro = str(exc)
    return render(request, 'acervo/buscar_cd.html', {
        'form': form, 'codigo': codigo, 'results': results, 'erro': erro,
        'pesquisou': submitted and form.is_valid(), 'manual_url': cadastro_manual_url(codigo, 'ean')})
