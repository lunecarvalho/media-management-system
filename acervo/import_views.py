from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from .models import ImportacaoCSV
from .csv_import import ler, resumo, confirmar, MAX_BYTES
from .forms import CSVUploadForm


def importar(request):
    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        upload = form.cleaned_data['arquivo']
        try:
            if upload.size > MAX_BYTES:
                raise ValidationError('CSV excede 1 MiB.')
            content = upload.read(MAX_BYTES + 1).decode('utf-8-sig')
            ler(content)
            batch = ImportacaoCSV.objects.create(usuario=request.user, conteudo=content)
            return redirect('acervo:previa_csv', pk=batch.pk)
        except (ValidationError, UnicodeDecodeError, csv.Error) as exc:
            form.add_error('arquivo', str(exc) if isinstance(exc, ValidationError) else 'Use um CSV válido em UTF-8.')
    return render(request, 'acervo/importar.html', {'form': form})


def previa(request, pk):
    batch = get_object_or_404(ImportacaoCSV, pk=pk, usuario=request.user)
    error = None
    if request.method == 'POST':
        try:
            confirmar(batch.pk, request.user)
            batch.refresh_from_db()
        except (ValidationError, IntegrityError) as exc:
            error = 'Conflito de dados. Revise a prévia.' if isinstance(exc, IntegrityError) else str(exc)
    rows = ler(batch.conteudo)
    return render(request, 'acervo/previa_csv.html', {'batch': batch, 'rows': rows,
        'resumo': resumo(rows), 'erro': error})

import csv
